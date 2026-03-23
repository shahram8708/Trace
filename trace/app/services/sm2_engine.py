from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple
from sqlalchemy.orm import joinedload
from sqlalchemy import func, case
from ..extensions import db
from ..models.concept import Concept
from ..models.review_event import ReviewEvent
from ..models.user import User


def sm2_update(ease_factor: float, interval: int, repetitions: int, quality: int) -> Tuple[float, int, int, date]:
    if quality < 3:
        new_repetitions = 0
        new_interval = 1
    else:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = max(1, round(interval * ease_factor))
        new_repetitions = repetitions + 1

    new_ease_factor = ease_factor + (0.1 - ((5 - quality) * (0.08 + ((5 - quality) * 0.02))))
    if new_ease_factor < 1.3:
        new_ease_factor = 1.3

    next_review_date = date.today() + timedelta(days=new_interval)
    return new_ease_factor, new_interval, new_repetitions, next_review_date


def compute_retention_strength(last_reviewed: datetime, interval: int) -> float:
    if not last_reviewed:
        return 0.0
    reviewed_date = last_reviewed.date() if isinstance(last_reviewed, datetime) else last_reviewed
    days_elapsed = (date.today() - reviewed_date).days
    if days_elapsed == 0:
        return 1.0
    stability = max(1.0, interval * 0.9)
    strength = math.exp(-(days_elapsed / stability))
    strength = max(0.0, min(1.0, strength))
    return round(strength, 3)


def get_due_concepts(user_id: int) -> List[Concept]:
    today = date.today()
    query = (
        db.select(Concept)
        .options(joinedload(Concept.source_item))
        .filter(
            Concept.user_id == user_id,
            Concept.is_active.is_(True),
            Concept.next_review_due.is_not(None),
            Concept.next_review_due <= today,
        )
        .order_by(Concept.next_review_due.asc())
    )
    return db.session.execute(query).scalars().all()


def get_new_concepts_for_session(user_id: int, daily_limit: int = 5) -> List[Concept]:
    query = (
        db.select(Concept)
        .options(joinedload(Concept.source_item))
        .filter(
            Concept.user_id == user_id,
            Concept.is_active.is_(True),
            Concept.sm2_repetitions == 0,
        )
        .order_by(Concept.next_review_due.asc().nullsfirst(), Concept.created_at.asc())
        .limit(daily_limit)
    )
    return db.session.execute(query).scalars().all()


def build_session_queue(user_id: int, max_new_per_session: int = 5) -> List[Concept]:
    due_concepts = get_due_concepts(user_id)
    new_concepts = get_new_concepts_for_session(user_id, daily_limit=max_new_per_session)
    seen = set()
    queue: List[Concept] = []
    for concept in due_concepts + new_concepts:
        if concept.id not in seen:
            queue.append(concept)
            seen.add(concept.id)
    return queue


def update_concept_after_review(
    concept: Concept,
    quality_rating: int,
    user_response_text: str,
    session_id: str,
):
    previous_interval = concept.sm2_interval
    new_ease, new_interval, new_reps, next_review_date = sm2_update(
        concept.sm2_ease_factor,
        concept.sm2_interval,
        concept.sm2_repetitions,
        quality_rating,
    )
    now = datetime.utcnow()
    concept.sm2_ease_factor = new_ease
    concept.sm2_interval = new_interval
    concept.sm2_repetitions = new_reps
    concept.next_review_due = next_review_date
    concept.last_reviewed = now
    concept.total_reviews = (concept.total_reviews or 0) + 1
    concept.is_mature = new_interval > 21
    concept.retention_strength = compute_retention_strength(now, new_interval)

    review_event = ReviewEvent(
        user_id=concept.user_id,
        concept_id=concept.id,
        reviewed_at=now,
        quality_rating=quality_rating,
        user_response_text=user_response_text,
        previous_interval=previous_interval,
        new_interval=new_interval,
        session_id=session_id,
    )
    db.session.add(review_event)

    user: User = concept.user  # type: ignore[assignment]
    if user:
        user.total_reviews_completed = (user.total_reviews_completed or 0) + 1

    return next_review_date


def get_overdue_concepts(user_id: int) -> List[Concept]:
    today = date.today()
    query = (
        db.select(Concept)
        .options(joinedload(Concept.source_item))
        .filter(
            Concept.user_id == user_id,
            Concept.is_active.is_(True),
            Concept.next_review_due.is_not(None),
            Concept.next_review_due < today,
        )
        .order_by(Concept.next_review_due.asc())
    )
    return db.session.execute(query).scalars().all()


def get_domain_retention_summary(user_id: int) -> List[Dict[str, object]]:
    query = (
        db.session.query(
            Concept.domain_tag.label("domain"),
            func.avg(Concept.retention_strength).label("avg_retention"),
            func.count(Concept.id).label("concept_count"),
            func.sum(case((Concept.is_mature.is_(True), 1), else_=0)).label("mature_count"),
        )
        .filter(Concept.user_id == user_id, Concept.is_active.is_(True))
        .group_by(Concept.domain_tag)
    )
    rows = query.all()
    results = [
        {
            "domain": row.domain or "Unspecified",
            "avg_retention": float(row.avg_retention or 0.0),
            "concept_count": int(row.concept_count or 0),
            "mature_count": int(row.mature_count or 0),
        }
        for row in rows
    ]
    results.sort(key=lambda r: r["avg_retention"])
    return results


def get_overall_retention_score(user_id: int) -> float:
    concepts = db.session.execute(
        db.select(Concept.retention_strength, Concept.total_reviews)
        .filter(Concept.user_id == user_id, Concept.is_active.is_(True))
    ).all()
    if not concepts:
        return 0.0
    weighted_sum = 0.0
    weight_total = 0.0
    for strength, reviews in concepts:
        weight = max(1.0, float(reviews or 0)) + 0.5
        weighted_sum += (strength or 0.0) * weight
        weight_total += weight
    if weight_total == 0:
        return 0.0
    score = (weighted_sum / weight_total) * 100
    return round(score, 1)
