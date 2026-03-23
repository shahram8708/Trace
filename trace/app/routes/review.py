from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, distinct, case
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..utils.decorators import onboarding_required
from ..services.sm2_engine import (
    build_session_queue,
    update_concept_after_review,
    get_overdue_concepts,
)
from ..services.streak_manager import update_streak_after_session, get_streak_display
from ..models.concept import Concept
from ..models.review_event import ReviewEvent


review_bp = Blueprint("review_bp", __name__, url_prefix="/review")


def _today_bounds():
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def _format_interval_label(interval: int) -> str:
    if interval <= 1:
        return "Tomorrow"
    if interval == 2:
        return "In 2 days"
    return f"In {interval} days"


@review_bp.route("/")
@login_required
@onboarding_required
def hub():
    queue = build_session_queue(current_user.id)
    queue_count = len(queue)
    overdue_concepts = get_overdue_concepts(current_user.id)
    overdue_count = len(overdue_concepts)
    streak_info = get_streak_display(current_user)

    start, end = _today_bounds()
    reviewed_today_count = db.session.execute(
        db.select(func.count(distinct(ReviewEvent.concept_id)))
        .filter(ReviewEvent.user_id == current_user.id, ReviewEvent.reviewed_at >= start, ReviewEvent.reviewed_at < end)
    ).scalar_one()

    concept_counts = db.session.execute(
        db.select(
            func.count(Concept.id),
            func.sum(case((Concept.is_mature.is_(True), 1), else_=0)),
            func.count(func.distinct(Concept.domain_tag)),
        ).filter(Concept.user_id == current_user.id, Concept.is_active.is_(True))
    ).one()
    total_concepts = concept_counts[0] or 0
    mature_concepts = int(concept_counts[1] or 0)
    domain_count = concept_counts[2] or 0

    domain_summary_rows = db.session.execute(
        db.session.query(
            Concept.domain_tag.label("domain"),
            func.avg(Concept.retention_strength).label("avg_retention"),
            func.count(Concept.id).label("concept_count"),
        )
        .filter(Concept.user_id == current_user.id, Concept.is_active.is_(True))
        .group_by(Concept.domain_tag)
    ).all()
    domain_summary = [
        {
            "domain": row.domain or "Unspecified",
            "avg_retention": float(row.avg_retention or 0.0),
            "concept_count": int(row.concept_count or 0),
        }
        for row in domain_summary_rows
    ]

    session_rows = db.session.execute(
        db.session.query(
            ReviewEvent.session_id,
            func.count(ReviewEvent.id).label("count"),
            func.max(ReviewEvent.reviewed_at).label("completed_at"),
        )
        .filter(ReviewEvent.user_id == current_user.id, ReviewEvent.session_id.is_not(None))
        .group_by(ReviewEvent.session_id)
        .order_by(func.max(ReviewEvent.reviewed_at).desc())
        .limit(5)
    ).all()
    recent_sessions = [
        {"session_id": row.session_id, "count": row.count, "completed_at": row.completed_at}
        for row in session_rows
    ]

    seven_days_ago = datetime.utcnow() - timedelta(days=6)
    recent_activity_rows = db.session.execute(
        db.session.query(func.date(ReviewEvent.reviewed_at).label("day"), func.count(ReviewEvent.id))
        .filter(ReviewEvent.user_id == current_user.id, ReviewEvent.reviewed_at >= seven_days_ago)
        .group_by(func.date(ReviewEvent.reviewed_at))
        .order_by(func.date(ReviewEvent.reviewed_at))
    ).all()
    recent_activity = {str(row.day): row[1] for row in recent_activity_rows}

    return render_template(
        "review/hub.html",
        queue_concepts=queue,
        queue_count=queue_count,
        overdue_count=overdue_count,
        streak_info=streak_info,
        reviewed_today_count=reviewed_today_count,
        has_due_concepts=queue_count > 0,
        total_concepts=total_concepts,
        mature_concepts=mature_concepts,
        domain_count=domain_count,
        domain_summary=domain_summary,
        recent_sessions=recent_sessions,
        recent_activity=recent_activity,
    )


@review_bp.route("/session")
@login_required
@onboarding_required
def session():
    session_id = uuid.uuid4().hex[:12]
    queue = build_session_queue(current_user.id)
    has_concepts = len(queue) > 0
    if not has_concepts:
        concepts_json = json.dumps({"session_id": session_id, "concepts": [], "total_count": 0, "streak": current_user.current_streak_days or 0})
        return render_template(
            "review/session.html",
            session_id=session_id,
            concepts_json=concepts_json,
            total_count=0,
            user_first_name=current_user.first_name or current_user.get_display_name(),
            streak_days=current_user.current_streak_days or 0,
            has_concepts=False,
        )

    concepts_payload = []
    for concept in queue:
        source_title = "Manual Entry"
        if concept.source_item and concept.source_item.title:
            source_title = concept.source_item.title
        concepts_payload.append(
            {
                "id": concept.id,
                "name": concept.name,
                "description": concept.description,
                "source_excerpt": concept.source_excerpt or "",
                "domain_tag": concept.domain_tag or "General",
                "source_title": source_title,
            }
        )

    concepts_json = json.dumps({
        "session_id": session_id,
        "concepts": concepts_payload,
        "total_count": len(concepts_payload),
        "streak": current_user.current_streak_days or 0,
    })

    return render_template(
        "review/session.html",
        session_id=session_id,
        concepts_json=concepts_json,
        total_count=len(concepts_payload),
        user_first_name=current_user.first_name or current_user.get_display_name(),
        streak_days=current_user.current_streak_days or 0,
        has_concepts=True,
    )


@review_bp.route("/submit", methods=["POST"])
@login_required
@onboarding_required
def submit_review():
    data = request.get_json(silent=True) or {}
    concept_id = data.get("concept_id")
    session_id = data.get("session_id")
    quality_rating = data.get("quality_rating")
    user_response_text = (data.get("user_response_text") or "").strip()

    if quality_rating not in {0, 1, 3, 5}:
        return jsonify({"error": "Invalid quality rating."}), 400
    try:
        concept_id = int(concept_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid concept."}), 400

    concept = db.session.get(Concept, concept_id)
    if not concept or concept.user_id != current_user.id:
        return jsonify({"error": "Concept not found."}), 404

    next_review_date = update_concept_after_review(concept, quality_rating, user_response_text, session_id)
    db.session.commit()

    interval_label = _format_interval_label(concept.sm2_interval)
    messages = {
        0: "No worries — it will come back around today.",
        1: "Getting there — it'll come back in a day.",
        3: f"Solid recall! {interval_label}.",
        5: f"Perfect! Locked in for {concept.sm2_interval} days.",
    }

    return jsonify(
        {
            "success": True,
            "next_review_date": interval_label,
            "new_interval": concept.sm2_interval,
            "new_ease_factor": concept.sm2_ease_factor,
            "is_mature": concept.is_mature,
            "message": messages.get(quality_rating, "Saved"),
        }
    )


@review_bp.route("/session/end", methods=["POST"])
@login_required
@onboarding_required
def end_session():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    total_reviewed = data.get("total_reviewed") or 0
    if not session_id:
        return jsonify({"error": "Session id required."}), 400

    update_streak_after_session(current_user)
    db.session.commit()

    rating_counts = db.session.execute(
        db.session.query(ReviewEvent.quality_rating, func.count(ReviewEvent.id))
        .filter(ReviewEvent.user_id == current_user.id, ReviewEvent.session_id == session_id)
        .group_by(ReviewEvent.quality_rating)
    ).all()
    counts_map = {row.quality_rating: row[1] for row in rating_counts}

    domain_rows = db.session.execute(
        db.session.query(Concept.domain_tag, func.count(ReviewEvent.id))
        .join(Concept, Concept.id == ReviewEvent.concept_id)
        .filter(ReviewEvent.user_id == current_user.id, ReviewEvent.session_id == session_id)
        .group_by(Concept.domain_tag)
    ).all()
    domains_reviewed = [
        {"domain": row.domain_tag or "Unspecified", "count": row[1]}
        for row in domain_rows
    ]

    is_new_record = (current_user.current_streak_days or 0) == (current_user.longest_streak_days or 0)

    summary = {
        "total_reviewed": total_reviewed,
        "again_count": counts_map.get(0, 0),
        "hard_count": counts_map.get(1, 0),
        "good_count": counts_map.get(3, 0),
        "easy_count": counts_map.get(5, 0),
        "domains_reviewed": domains_reviewed,
    }

    return jsonify(
        {
            "success": True,
            "streak": current_user.current_streak_days or 0,
            "longest_streak": current_user.longest_streak_days or 0,
            "is_new_streak_record": is_new_record,
            "summary": summary,
        }
    )


@review_bp.route("/history")
@login_required
@onboarding_required
def history():
    page = request.args.get("page", 1, type=int)
    query = (
        db.select(ReviewEvent)
        .options(joinedload(ReviewEvent.concept))
        .filter(ReviewEvent.user_id == current_user.id)
        .order_by(ReviewEvent.reviewed_at.desc())
    )
    pagination = db.paginate(query, page=page, per_page=20, error_out=False)
    items = pagination.items

    grouped = defaultdict(list)
    for event in items:
        concept = event.concept
        if concept is None:
            continue
        day = event.reviewed_at.date()
        grouped[day].append((event, concept))
    grouped_events = dict(sorted(grouped.items(), key=lambda kv: kv[0], reverse=True))

    total_all_time = db.session.execute(
        db.select(func.count(ReviewEvent.id)).filter(ReviewEvent.user_id == current_user.id)
    ).scalar_one()
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    total_month = db.session.execute(
        db.select(func.count(ReviewEvent.id)).filter(
            ReviewEvent.user_id == current_user.id, ReviewEvent.reviewed_at >= thirty_days_ago
        )
    ).scalar_one()
    total_week = db.session.execute(
        db.select(func.count(ReviewEvent.id)).filter(
            ReviewEvent.user_id == current_user.id, ReviewEvent.reviewed_at >= seven_days_ago
        )
    ).scalar_one()
    avg_daily_30 = round((total_month or 0) / 30, 1) if total_month else 0.0

    heatmap_rows = db.session.execute(
        db.session.query(func.date(ReviewEvent.reviewed_at), func.count(ReviewEvent.id))
        .filter(ReviewEvent.user_id == current_user.id, ReviewEvent.reviewed_at >= thirty_days_ago)
        .group_by(func.date(ReviewEvent.reviewed_at))
    ).all()
    heatmap_map = {}
    for row in heatmap_rows:
        key = row[0]
        if isinstance(key, str):
            try:
                key = datetime.strptime(key, "%Y-%m-%d").date()
            except ValueError:
                continue
        elif isinstance(key, datetime):
            key = key.date()
        heatmap_map[key] = row[1]
    heatmap_data = []
    for i in range(30):
        day = date.today() - timedelta(days=29 - i)
        heatmap_data.append({"date": day.isoformat(), "count": int(heatmap_map.get(day, 0))})

    return render_template(
        "review/history.html",
        pagination=pagination,
        grouped_events=grouped_events,
        total_all_time=total_all_time,
        total_week=total_week,
        total_month=total_month,
        avg_daily_30=avg_daily_30,
        heatmap_data=heatmap_data,
    )


@review_bp.route("/overdue")
@login_required
@onboarding_required
def overdue():
    overdue_concepts = get_overdue_concepts(current_user.id)
    grouped = defaultdict(list)
    for concept in overdue_concepts:
        domain = concept.domain_tag or "Unspecified"
        grouped[domain].append(concept)
    grouped_domains = dict(sorted(grouped.items(), key=lambda kv: kv[0]))
    return render_template(
        "review/overdue.html",
        overdue_concepts=overdue_concepts,
        grouped_domains=grouped_domains,
        today=date.today(),
    )
