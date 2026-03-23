from datetime import datetime, timedelta, date
from typing import List
from flask import current_app
from sqlalchemy import func

from celery_worker import celery
from .extensions import db
from .models.user import User
from .models.source_item import SourceItem
from .models.ai_extraction_queue import AIExtractionQueue
from .models.concept import Concept
from .models.review_event import ReviewEvent
from .models.application_event import ApplicationEvent
from .services.ai_extractor import extract_concepts_from_text
from .services.connection_suggester import compute_and_store_suggestions
from .services.report_generator import generate_weekly_report_data
from .services.email_service import (
    send_weekly_report_email,
    send_review_reminder_email,
    send_application_reminder_email,
)
from .services.application_reminder import generate_application_reminders
from .services.sm2_engine import compute_retention_strength


@celery.task(name="trace.app.tasks.process_ai_extraction_async", bind=True)
def process_ai_extraction_async(self, source_item_id: int):
    print(f"\n{'#'*60}")
    print(f"[CELERY TASK] process_ai_extraction_async STARTED")
    print(f"[CELERY TASK] source_item_id: {source_item_id}")
    print(f"[CELERY TASK] Timestamp: {datetime.utcnow().isoformat()}")
    print(f"[CELERY TASK] Worker: {self.request.hostname if hasattr(self, 'request') else 'unknown'}")
    print(f"{'#'*60}\n")

    queue_entry = None
    try:
        source_item = db.session.get(SourceItem, source_item_id)
        if not source_item:
            current_app.logger.error("SourceItem %s not found for extraction", source_item_id)
            return

        queue_entry = AIExtractionQueue(source_item_id=source_item.id, status="processing")
        db.session.add(queue_entry)
        db.session.commit()

        concepts = extract_concepts_from_text(
            source_item.full_text or "",
            domain_tags=source_item.domain_tags or [],
            source_title=source_item.title,
        )

        print(
            f"[CELERY TASK] extract_concepts_from_text returned: {type(concepts)} with {len(concepts) if concepts else 0} items"
        )
        if concepts:
            for i, concept in enumerate(concepts):
                print(
                    f"[CELERY TASK] Concept {i+1}: name='{concept.get('name', 'MISSING')}' | desc_length={len(concept.get('description',''))}"
                )
        else:
            print(f"[CELERY TASK] WARNING: Empty result — extraction returned no concepts")

        if concepts:
            queue_entry.extracted_concepts_json = concepts
            queue_entry.status = "completed"
            queue_entry.completed_at = datetime.utcnow()
            source_item.is_processed = True
            source_item.concept_count = len([c for c in concepts if c.get("name")])
            db.session.commit()
            print(f"[CELERY TASK] Storing {len(concepts)} concepts to AIExtractionQueue id={queue_entry.id}")
            print(f"[CELERY TASK] Setting status to: completed")
            current_app.logger.info("AI extraction completed for source_item %s", source_item.id)
        else:
            queue_entry.status = "failed"
            queue_entry.error_message = "No concepts were extracted from the provided content."
            queue_entry.completed_at = datetime.utcnow()
            source_item.is_processed = True
            db.session.commit()
            print(f"[CELERY TASK] Storing 0 concepts to AIExtractionQueue id={queue_entry.id}")
            print(f"[CELERY TASK] Setting status to: failed")
            current_app.logger.warning("AI extraction returned no concepts for source_item %s", source_item.id)

        print(f"\n{'#'*60}")
        print(f"[CELERY TASK] process_ai_extraction_async COMPLETED")
        print(f"[CELERY TASK] source_item_id: {source_item_id}")
        print(f"[CELERY TASK] Final status: {queue_entry.status if queue_entry else 'unknown'}")
        print(f"[CELERY TASK] Concepts stored: {len(concepts) if concepts else 0}")
        print(f"{'#'*60}\n")
    except Exception as exc:  # pragma: no cover - defensive logging
        db.session.rollback()
        if queue_entry:
            try:
                queue_entry.status = "failed"
                queue_entry.error_message = str(exc)
                queue_entry.completed_at = datetime.utcnow()
                db.session.commit()
            except Exception:
                db.session.rollback()
        current_app.logger.exception("AI extraction task failed for source_item %s", source_item_id)


@celery.task(name="trace.app.tasks.compute_connection_suggestions_for_user")
def compute_connection_suggestions_for_user(user_id: int):
    try:
        compute_and_store_suggestions(user_id)
    except Exception:  # pragma: no cover - defensive logging
        current_app.logger.exception("Connection suggestion computation failed for user %s", user_id)


@celery.task(name="trace.app.tasks.send_weekly_reports_to_all_users")
def send_weekly_reports_to_all_users():
    batch_size = 50
    try:
        premium_users: List[User] = (
            db.session.query(User)
            .filter(User.is_premium.is_(True), User.is_verified.is_(True))
            .order_by(User.id.asc())
            .all()
        )
    except Exception:  # pragma: no cover
        current_app.logger.exception("Failed to load premium users for weekly reports")
        return

    sent = 0
    for idx in range(0, len(premium_users), batch_size):
        chunk = premium_users[idx : idx + batch_size]
        for user in chunk:
            preferences = getattr(user, "notifications_preferences", {}) or {}
            if preferences.get("weekly_report_enabled", True) is False:
                continue
            try:
                report_data = generate_weekly_report_data(user.id)
                send_weekly_report_email(user, report_data)
                sent += 1
            except Exception:  # pragma: no cover
                current_app.logger.exception("Failed sending weekly report for user %s", user.id)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Commit failed after weekly report batch")
    current_app.logger.info("Weekly reports dispatched: %s", sent)


@celery.task(name="trace.app.tasks.send_review_reminders")
def send_review_reminders():
    now_utc = datetime.utcnow()
    current_hour = now_utc.strftime("%H")
    today = date.today()
    try:
        candidates: List[User] = (
            db.session.query(User)
            .filter(User.is_verified.is_(True), User.review_reminder_time.isnot(None))
            .all()
        )
    except Exception:  # pragma: no cover
        current_app.logger.exception("Failed to load users for review reminders")
        return

    reminders_sent = 0
    for user in candidates:
        preferences = getattr(user, "notifications_preferences", {}) or {}
        if preferences.get("review_reminder_enabled", True) is False:
            continue
        reminder_time = (user.review_reminder_time or "").split(":")[0]
        if reminder_time != current_hour:
            continue

        due_count = db.session.scalar(
            db.select(func.count(Concept.id)).filter(
                Concept.user_id == user.id,
                Concept.is_active.is_(True),
                Concept.next_review_due <= today,
            )
        ) or 0
        if due_count == 0:
            continue

        reviewed_today = (
            db.session.query(ReviewEvent)
            .filter(
                ReviewEvent.user_id == user.id,
                func.date(ReviewEvent.reviewed_at) == today,
            )
            .count()
        )
        if reviewed_today:
            continue

        try:
            send_review_reminder_email(user, due_count)
            reminders_sent += 1
        except Exception:  # pragma: no cover
            current_app.logger.exception("Failed sending review reminder for user %s", user.id)
    current_app.logger.info("Review reminders sent: %s", reminders_sent)


@celery.task(name="trace.app.tasks.update_all_retention_scores")
def update_all_retention_scores():
    batch_size = 500
    updated = 0
    try:
        query = db.select(Concept).filter(Concept.is_active.is_(True))
        concepts = db.session.execute(query).scalars().all()
    except Exception:  # pragma: no cover
        current_app.logger.exception("Failed to load concepts for retention update")
        return

    for concept in concepts:
        if not concept.last_reviewed:
            continue
        concept.retention_strength = compute_retention_strength(concept.last_reviewed, concept.sm2_interval)
        concept.is_mature = concept.sm2_interval > 21
        updated += 1
        if updated % batch_size == 0:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Commit failed during retention update batch")
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Final commit failed for retention update")
    current_app.logger.info("Retention scores updated for %s concepts", updated)


@celery.task(name="trace.app.tasks.send_application_reminders_for_user")
def send_application_reminders_for_user(user_id: int):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return
        projects = user.projects if user.projects else []
        for project in projects:
            if not project.is_active:
                continue
            try:
                events = generate_application_reminders(user_id, project.id)
                for event in events:
                    preferences = getattr(user, "notifications_preferences", {}) or {}
                    if preferences.get("application_reminders_enabled", True) is False:
                        continue
                    send_application_reminder_email(user, event.concept, event.project, event.prompt_text)
            except Exception:  # pragma: no cover
                current_app.logger.exception(
                    "Failed to generate application reminders for user %s project %s", user_id, project.id
                )
        db.session.commit()
    except Exception:  # pragma: no cover
        db.session.rollback()
        current_app.logger.exception("Application reminder task failed for user %s", user_id)


@celery.task(name="trace.app.tasks.generate_connection_suggestions_all_users")
def generate_connection_suggestions_all_users():
    since = datetime.utcnow() - timedelta(hours=6)
    try:
        users = (
            db.session.query(User)
            .join(Concept, Concept.user_id == User.id)
            .filter(Concept.created_at >= since)
            .distinct()
            .all()
        )
    except Exception:  # pragma: no cover
        current_app.logger.exception("Failed to load users for connection suggestions")
        return

    for user in users:
        try:
            compute_connection_suggestions_for_user.delay(user.id)
        except Exception:  # pragma: no cover
            current_app.logger.exception("Failed to enqueue connection suggestion for user %s", user.id)
