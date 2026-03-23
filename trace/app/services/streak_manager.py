from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict
from sqlalchemy import func
from ..extensions import db
from ..models.review_event import ReviewEvent
from ..models.concept import Concept


def _today_bounds():
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def update_streak_after_session(user) -> None:
    start, end = _today_bounds()
    latest_event = db.session.execute(
        db.select(ReviewEvent.reviewed_at)
        .filter(ReviewEvent.user_id == user.id)
        .order_by(ReviewEvent.reviewed_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_event is None:
        user.current_streak_days = 1
        user.streak_at_risk = False
    else:
        delta_days = (start.date() - latest_event.date()).days
        if delta_days == 0:
            # Already reviewed today; ensure streak counted once
            if not user.current_streak_days:
                user.current_streak_days = 1
            user.streak_at_risk = False
        elif delta_days == 1:
            user.current_streak_days = (user.current_streak_days or 0) + 1
            user.streak_at_risk = False
        elif delta_days == 2:
            user.streak_at_risk = True
            if not user.current_streak_days:
                user.current_streak_days = 1
        else:
            user.current_streak_days = 1
            user.streak_at_risk = False

    if user.current_streak_days > (user.longest_streak_days or 0):
        user.longest_streak_days = user.current_streak_days


def get_streak_display(user) -> Dict[str, object]:
    start, end = _today_bounds()
    today_events = db.session.execute(
        db.select(func.count(ReviewEvent.id))
        .filter(ReviewEvent.user_id == user.id, ReviewEvent.reviewed_at >= start, ReviewEvent.reviewed_at < end)
    ).scalar_one()
    due_count = db.session.execute(
        db.select(func.count(Concept.id))
        .filter(
            Concept.user_id == user.id,
            Concept.is_active.is_(True),
            Concept.next_review_due.is_not(None),
            Concept.next_review_due <= date.today(),
        )
    ).scalar_one()
    is_at_risk = today_events == 0 and due_count > 0
    current = user.current_streak_days or 0
    if current == 0:
        message = "Start your streak today!"
    elif current < 7:
        message = "Building momentum — keep going!"
    elif current < 30:
        message = f"{current} day streak — impressive consistency!"
    else:
        message = f"{current} day streak — you're building real expertise!"

    return {
        "current_streak": current,
        "longest_streak": user.longest_streak_days or 0,
        "is_at_risk": is_at_risk,
        "streak_message": message,
    }


def check_and_apply_grace_period(user) -> bool:
    start, end = _today_bounds()
    last_event = db.session.execute(
        db.select(ReviewEvent.reviewed_at)
        .filter(ReviewEvent.user_id == user.id, ReviewEvent.reviewed_at < start)
        .order_by(ReviewEvent.reviewed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not last_event:
        user.streak_at_risk = False
        return False
    delta_days = (start.date() - last_event.date()).days
    if delta_days == 2:
        user.streak_at_risk = True
        return True
    user.streak_at_risk = False
    if delta_days > 2:
        user.current_streak_days = 1
    return False
