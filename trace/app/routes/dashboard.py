from __future__ import annotations

from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, distinct, case
from ..extensions import db
from ..services.sm2_engine import build_session_queue, get_overdue_concepts, get_domain_retention_summary, get_overall_retention_score
from ..services.streak_manager import get_streak_display
from ..utils.free_tier import check_free_tier_limits
from ..utils.decorators import onboarding_required
from ..models.concept import Concept
from ..models.source_item import SourceItem
from ..models.review_event import ReviewEvent


dashboard_bp = Blueprint("dashboard_bp", __name__)


def _today_bounds():
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def _time_of_day_label(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    return "evening"


@dashboard_bp.route("/dashboard")
@login_required
@onboarding_required
def dashboard():
    queue = build_session_queue(current_user.id)
    queue_count = len(queue)

    start, end = _today_bounds()
    reviewed_today_count = db.session.execute(
        db.select(func.count(distinct(ReviewEvent.concept_id)))
        .filter(ReviewEvent.user_id == current_user.id, ReviewEvent.reviewed_at >= start, ReviewEvent.reviewed_at < end)
    ).scalar_one()

    domain_summary = get_domain_retention_summary(current_user.id)
    domain_summary_sorted = sorted(domain_summary, key=lambda d: d.get("concept_count", 0), reverse=True)
    domain_summary_top = domain_summary_sorted[:5]

    overall_retention = get_overall_retention_score(current_user.id)

    counts = db.session.execute(
        db.select(
            func.count(Concept.id),
            func.sum(case((Concept.is_mature.is_(True), 1), else_=0)),
            func.count(distinct(Concept.domain_tag)),
        ).filter(Concept.user_id == current_user.id, Concept.is_active.is_(True))
    ).one()
    total_active = counts[0] or 0
    mature_count = int(counts[1] or 0)
    domain_count = counts[2] or 0

    recent_sources = db.session.execute(
        db.select(SourceItem)
        .filter(SourceItem.user_id == current_user.id)
        .order_by(SourceItem.import_date.desc())
        .limit(3)
    ).scalars().all()

    streak_info = get_streak_display(current_user)
    overdue_count = len(get_overdue_concepts(current_user.id))
    limits = check_free_tier_limits(current_user)

    earliest_due = db.session.execute(
        db.select(Concept.next_review_due)
        .filter(Concept.user_id == current_user.id, Concept.is_active.is_(True), Concept.next_review_due.is_not(None))
        .order_by(Concept.next_review_due.asc())
        .limit(1)
    ).scalar_one_or_none()

    time_of_day = _time_of_day_label(datetime.utcnow())

    return render_template(
        "dashboard/main.html",
        queue_count=queue_count,
        reviewed_today_count=reviewed_today_count,
        domain_summary=domain_summary_top,
        overall_retention=overall_retention,
        total_active=total_active,
        mature_count=mature_count,
        domain_count=domain_count,
        recent_sources=recent_sources,
        streak_info=streak_info,
        overdue_count=overdue_count,
        limits=limits,
        earliest_due=earliest_due,
        time_of_day=time_of_day,
        current_date=date.today(),
    )


@dashboard_bp.route("/dashboard/snapshot")
@login_required
@onboarding_required
def dashboard_snapshot():
    queue = build_session_queue(current_user.id)
    due_count = len(queue)

    counts = db.session.execute(
        db.select(
            func.count(Concept.id),
            func.sum(case((Concept.is_mature.is_(True), 1), else_=0)),
            func.count(distinct(Concept.domain_tag)),
        ).filter(Concept.user_id == current_user.id, Concept.is_active.is_(True))
    ).one()
    active_count = counts[0] or 0
    mature_count = int(counts[1] or 0)
    domain_count = counts[2] or 0

    recent_imports = db.session.execute(
        db.select(SourceItem)
        .filter(SourceItem.user_id == current_user.id)
        .order_by(SourceItem.import_date.desc())
        .limit(5)
    ).scalars().all()

    stats = {
        "due_count": due_count,
        "active_count": active_count,
        "domain_count": domain_count,
        "mature_count": mature_count,
        "streak": current_user.current_streak_days or 0,
    }

    return render_template("dashboard.html", stats=stats, recent_imports=recent_imports)
