from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List

from sqlalchemy import func

from ..extensions import db
from ..models.review_event import ReviewEvent
from ..models.concept import Concept
from ..models.user import User
from ..services.sm2_engine import get_overall_retention_score


def _week_range(today: date):
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    prev_start = start - timedelta(days=7)
    prev_end = start - timedelta(days=1)
    return start, end, prev_start, prev_end


def generate_weekly_report_data(user_id: int) -> Dict[str, object]:
    today = date.today()
    week_start, week_end, prev_week_start, prev_week_end = _week_range(today)

    def _count_reviews(start_d: date, end_d: date) -> int:
        return (
            db.session.query(func.count(ReviewEvent.id))
            .filter(
                ReviewEvent.user_id == user_id,
                func.date(ReviewEvent.reviewed_at) >= start_d,
                func.date(ReviewEvent.reviewed_at) <= end_d,
            )
            .scalar()
            or 0
        )

    reviews_this_week = _count_reviews(week_start, week_end)
    reviews_last_week = _count_reviews(prev_week_start, prev_week_end)

    # Domain retention changes
    domain_current = defaultdict(list)
    domain_prev = defaultdict(list)

    concepts = db.session.query(Concept).filter(Concept.user_id == user_id, Concept.is_active.is_(True)).all()
    for concept in concepts:
        if concept.last_reviewed:
            last_review_date = concept.last_reviewed.date()
            if week_start <= last_review_date <= week_end:
                domain_current[concept.domain_tag or "Unspecified"].append(concept.retention_strength or 0.0)
            elif prev_week_start <= last_review_date <= prev_week_end:
                domain_prev[concept.domain_tag or "Unspecified"].append(concept.retention_strength or 0.0)

    domain_performance: List[Dict[str, object]] = []
    for domain in set(list(domain_current.keys()) + list(domain_prev.keys())):
        current_avg = sum(domain_current.get(domain, []) or [0]) / max(len(domain_current.get(domain, [])) or 1, 1)
        prev_avg = sum(domain_prev.get(domain, []) or [0]) / max(len(domain_prev.get(domain, [])) or 1, 1)
        change = (current_avg - prev_avg) * 100
        domain_performance.append(
            {
                "domain": domain,
                "current_avg": round(current_avg, 3),
                "previous_avg": round(prev_avg, 3),
                "change_percent": round(change, 1),
            }
        )

    overdue_concepts = (
        db.session.query(Concept)
        .filter(
            Concept.user_id == user_id,
            Concept.is_active.is_(True),
            Concept.next_review_due.isnot(None),
            Concept.next_review_due < today,
        )
        .order_by(Concept.next_review_due.asc())
        .limit(10)
        .all()
    )
    overdue_list = [
        {
            "name": c.name,
            "domain": c.domain_tag,
            "days_overdue": (today - c.next_review_due).days if c.next_review_due else 0,
        }
        for c in overdue_concepts
    ]

    # If nothing is overdue, surface the next few items that will become due so the UI is never empty.
    upcoming_concepts = []
    if not overdue_list:
        upcoming_concepts = (
            db.session.query(Concept)
            .filter(
                Concept.user_id == user_id,
                Concept.is_active.is_(True),
                Concept.next_review_due.isnot(None),
                Concept.next_review_due >= today,
            )
            .order_by(Concept.next_review_due.asc())
            .limit(5)
            .all()
        )
    upcoming_list = [
        {
            "name": c.name,
            "domain": c.domain_tag,
            "days_until_due": (c.next_review_due - today).days if c.next_review_due else 0,
        }
        for c in upcoming_concepts
    ]

    new_concepts = (
        db.session.query(Concept)
        .filter(
            Concept.user_id == user_id,
            Concept.created_at >= datetime.combine(week_start, datetime.min.time()),
            Concept.created_at <= datetime.combine(week_end, datetime.max.time()),
        )
        .order_by(Concept.created_at.desc())
        .all()
    )
    new_concepts_list = [
        {"name": c.name, "domain": c.domain_tag, "source_title": c.source_item.title if c.source_item else "Manual"}
        for c in new_concepts
    ]

    concept_of_week = None
    cow_query = (
        db.session.query(ReviewEvent.concept_id, func.count(ReviewEvent.id).label("cnt"))
        .filter(
            ReviewEvent.user_id == user_id,
            func.date(ReviewEvent.reviewed_at) >= week_start,
            func.date(ReviewEvent.reviewed_at) <= week_end,
        )
        .group_by(ReviewEvent.concept_id)
        .order_by(func.count(ReviewEvent.id).desc())
        .first()
    )
    if cow_query:
        concept_of_week = db.session.get(Concept, cow_query.concept_id)

    activity_data: List[Dict[str, object]] = []
    for i in range(30):
        day = today - timedelta(days=29 - i)
        count = (
            db.session.query(func.count(ReviewEvent.id))
            .filter(ReviewEvent.user_id == user_id, func.date(ReviewEvent.reviewed_at) == day)
            .scalar()
            or 0
        )
        activity_data.append({"date": day.isoformat(), "count": int(count)})

    user = db.session.get(User, user_id)
    overall_now = get_overall_retention_score(user_id)
    reviewed_last_week_concepts = [c for c in concepts if c.last_reviewed and prev_week_start <= c.last_reviewed.date() <= prev_week_end]
    if reviewed_last_week_concepts:
        overall_last_week = sum(c.retention_strength or 0.0 for c in reviewed_last_week_concepts) / len(reviewed_last_week_concepts)
    else:
        overall_last_week = 0.0

    data = {
        "week_start": week_start,
        "week_end": week_end,
        "reviews_this_week": reviews_this_week,
        "reviews_last_week": reviews_last_week,
        "domain_performance": domain_performance,
        "overdue_concepts": overdue_list,
        "upcoming_due": upcoming_list,
        "new_concepts": new_concepts_list,
        "concept_of_week": concept_of_week,
        "activity_data": activity_data,
        "current_streak": user.current_streak_days if user else 0,
        "longest_streak": user.longest_streak_days if user else 0,
        "overall_retention": round(overall_now * 100, 1) if overall_now is not None else 0,
        "overall_retention_last_week": round(overall_last_week * 100, 1),
        "mature_concepts": len([c for c in concepts if c.is_mature]),
        "active_concepts": len(concepts),
    }
    return data
