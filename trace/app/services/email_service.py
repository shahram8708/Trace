import os
from datetime import datetime
from flask import current_app, render_template
from flask_mail import Message

from ..extensions import mail


def _base_url() -> str:
    return os.getenv("BASE_URL", "https://trace.onrender.com/")


def _send_email(user, subject: str, html_template: str, text_template: str = None, **context):
    try:
        html_body = render_template(html_template, user=user, base_url=_base_url(), **context)
        text_body = render_template(text_template, user=user, base_url=_base_url(), **context) if text_template else None
        msg = Message(subject=subject, recipients=[user.email])
        msg.html = html_body
        if text_body:
            msg.body = text_body
        mail.send(msg)
    except Exception:  # pragma: no cover - email should never crash callers
        current_app.logger.exception("Email send failed: %s", subject)


def send_verification_email(user, token: str):
    verify_link = f"{_base_url()}/verify/{token}"
    _send_email(
        user,
        "Please verify your Trace account",
        "emails/verify_email.html",
        "emails/verify_email.txt",
        verify_link=verify_link,
    )


def send_password_reset_email(user, token: str):
    reset_link = f"{_base_url()}/reset/{token}"
    _send_email(
        user,
        "Reset your Trace password",
        "emails/password_reset.html",
        "emails/password_reset.txt",
        reset_link=reset_link,
    )


def send_weekly_report_email(user, report_data):
    date_range = f"{report_data['week_start'].strftime('%b %d')} – {report_data['week_end'].strftime('%b %d, %Y')}"
    _send_email(
        user,
        f"Your Weekly Trace Report — {date_range}",
        "emails/weekly_report.html",
        None,
        report_data=report_data,
        date_range=date_range,
    )


def send_review_reminder_email(user, due_count: int):
    _send_email(
        user,
        f"You have {due_count} concepts ready for review",
        "emails/review_reminder.html",
        None,
        due_count=due_count,
    )


def send_application_reminder_email(user, concept, project, prompt_text: str):
    _send_email(
        user,
        f"Apply your knowledge of {concept.name} to {project.name}",
        "emails/application_reminder.html",
        None,
        concept=concept,
        project=project,
        prompt_text=prompt_text,
    )


def send_subscription_confirmation_email(user):
    amount = "₹999" if user.subscription_tier == "monthly" else "₹8,999"
    _send_email(
        user,
        "Welcome to Trace Pro! 🎉",
        "emails/subscription_confirmation.html",
        None,
        amount=amount,
    )


def send_subscription_cancellation_email(user):
    _send_email(
        user,
        "Your Trace Pro subscription has been cancelled",
        "emails/subscription_cancellation.html",
        None,
        cancel_date=user.subscription_expires,
    )


def send_account_deletion_email(user):
    _send_email(
        user,
        "Your Trace account has been deleted",
        "emails/account_deleted.html",
        None,
    )


def send_payment_failure_email(user):
    _send_email(
        user,
        "Payment failed for your Trace Pro subscription",
        "emails/payment_failed.html",
        None,
    )
