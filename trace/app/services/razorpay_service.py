import hmac
import hashlib
import os
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

import razorpay
from flask import current_app
from sqlalchemy import or_

from ..extensions import db
from ..models.user import User
from .email_service import send_payment_failure_email, send_subscription_confirmation_email


def get_razorpay_client() -> razorpay.Client:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise RuntimeError("Razorpay credentials are not configured")
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_customer(user: User) -> dict:
    client = get_razorpay_client()
    if user.razorpay_customer_id:
        return {"id": user.razorpay_customer_id}
    customer = client.customer.create({"name": user.get_display_name(), "email": user.email})
    user.razorpay_customer_id = customer.get("id")
    db.session.commit()
    return customer


def create_subscription(user: User, plan_type: str) -> dict:
    if plan_type not in {"monthly", "annual"}:
        raise ValueError("Invalid plan type")

    plan_id = _resolve_plan_id(plan_type)

    customer = create_razorpay_customer(user)
    client = get_razorpay_client()
    total_count = 12 if plan_type == "monthly" else 3
    subscription = client.subscription.create(
        {
            "plan_id": plan_id,
            "customer_notify": 1,
            "total_count": total_count,
            "customer_id": customer.get("id"),
        }
    )
    user.razorpay_subscription_id = subscription.get("id")
    db.session.commit()
    return subscription


def verify_payment_signature(razorpay_payment_id: str, razorpay_subscription_id: str, razorpay_signature: str) -> bool:
    client = get_razorpay_client()
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_subscription_id": razorpay_subscription_id,
                "razorpay_signature": razorpay_signature,
            }
        )
        return True
    except Exception:
        return False


def is_captured_payment_for_subscription(razorpay_payment_id: str, subscription_id: str) -> tuple[bool, Optional[str]]:
    """Fetch payment from Razorpay, confirm capture, and return (ok, subscription_id_seen)."""
    client = get_razorpay_client()
    payment = client.payment.fetch(razorpay_payment_id)
    if not payment:
        return False, None
    status_ok = payment.get("status") == "captured"
    seen_sub_id = payment.get("subscription_id")
    # Accept capture as authoritative; subscription match is only informational to avoid false negatives
    return bool(status_ok), seen_sub_id


def activate_premium(user: User, subscription_id: str, plan_type: str) -> None:
    user.is_premium = True
    user.subscription_tier = plan_type
    user.razorpay_subscription_id = subscription_id
    days = 31 if plan_type == "monthly" else 366
    user.subscription_expires = datetime.utcnow() + timedelta(days=days)
    user.subscription_cancel_at = None
    db.session.commit()
    send_subscription_confirmation_email(user)


def _cancel_pending_refunds_for_subscription(subscription_id: str, client: razorpay.Client) -> None:
    """Best-effort cancellation of pending refunds so we retain collected revenue.

    Razorpay only allows cancelling refunds that are still pending. Processed refunds
    cannot be undone; we just log those cases.
    """

    try:
        payments = client.payment.all({"subscription_id": subscription_id, "count": 20}).get("items", [])
    except Exception:
        current_app.logger.exception("Failed to fetch payments while cancelling refunds for %s", subscription_id)
        return

    for payment in payments:
        refunds_container = payment.get("refunds") or {}
        for refund in refunds_container.get("items", []):
            if refund.get("status") != "pending":
                continue
            refund_id = refund.get("id")
            if not refund_id:
                continue
            try:
                client.refund.cancel(refund_id)
            except Exception:
                current_app.logger.exception("Failed to cancel pending refund %s for subscription %s", refund_id, subscription_id)


def cancel_subscription(user: User) -> bool:
    """Cancel a Razorpay subscription and keep collected payments (no auto-refund).

    - Stops further renewals at the cycle end so revenue is retained.
    - Cancels any pending refunds (processed refunds cannot be reversed).
    - Keeps access until the end of the already-paid period; local flags mirror that state.
    Returns True on success so the caller can decide whether to show a failure message.
    """

    now = datetime.utcnow()

    # If we do not have a subscription id, just revoke local access to avoid dangling premium flags.
    if not user.razorpay_subscription_id:
        user.is_premium = False
        user.subscription_tier = "free"
        user.subscription_expires = None
        user.subscription_cancel_at = now
        db.session.commit()
        return True

    client = get_razorpay_client()
    try:
        subscription_entity = client.subscription.fetch(user.razorpay_subscription_id)
    except Exception:
        current_app.logger.exception("Failed to fetch Razorpay subscription %s", user.razorpay_subscription_id)
        db.session.rollback()
        return False

    # If Razorpay already shows it as cancelled/completed, mirror locally and exit early.
    if subscription_entity.get("status") in {"cancelled", "completed"}:
        deactivate_premium(user)
        user.subscription_cancel_at = now
        db.session.commit()
        return True

    try:
        # cancel_at_cycle_end=1 ensures Razorpay stops billing after the current period and avoids automatic refunds.
        response = client.subscription.cancel(user.razorpay_subscription_id, {"cancel_at_cycle_end": 1})
    except Exception:
        current_app.logger.exception("Failed to cancel Razorpay subscription %s", user.razorpay_subscription_id)
        db.session.rollback()
        return False

    # Best-effort: stop any pending refunds that may have been queued during cancellation.
    _cancel_pending_refunds_for_subscription(user.razorpay_subscription_id, client)

    # Mirror remote state locally. Access is revoked immediately to avoid stale premium access flags.
    current_end = response.get("current_end") or subscription_entity.get("current_end")
    cancel_effective_at = (
        datetime.utcfromtimestamp(int(current_end))
        if current_end
        else (user.subscription_expires or now)
    )
    user.subscription_cancel_at = cancel_effective_at
    user.is_premium = False
    user.subscription_tier = user.subscription_tier or "free"
    user.subscription_expires = cancel_effective_at
    db.session.commit()
    return True


def deactivate_premium(user: User) -> None:
    user.is_premium = False
    user.subscription_tier = "free"
    user.subscription_expires = None
    user.subscription_cancel_at = None
    db.session.commit()


def reactivate_subscription(user: User, plan_type: Optional[str] = None) -> dict:
    """Restart billing for a user who cancelled by creating a fresh subscription."""

    if user.is_premium and user.subscription_cancel_at is None:
        return {}

    chosen_plan = plan_type or user.subscription_tier or "monthly"
    if chosen_plan not in {"monthly", "annual"}:
        chosen_plan = "monthly"

    new_subscription = create_subscription(user, chosen_plan)
    activate_premium(user, new_subscription.get("id"), chosen_plan)
    return new_subscription


def verify_webhook_signature(payload_body: bytes, razorpay_signature: str) -> bool:
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        return False
    digest = hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, razorpay_signature)


def _find_user(subscription_id: Optional[str], customer_id: Optional[str]) -> Optional[User]:
    query = db.session.query(User)
    filters = []
    if subscription_id:
        filters.append(User.razorpay_subscription_id == subscription_id)
    if customer_id:
        filters.append(User.razorpay_customer_id == customer_id)
    if not filters:
        return None
    return query.filter(or_(*filters)).first() if len(filters) > 1 else query.filter(filters[0]).first()


def _plan_type_from_event(plan_id: Optional[str]) -> str:
    if not plan_id:
        return "monthly"
    try:
        if plan_id == _resolve_plan_id("annual"):
            return "annual"
    except Exception:
        current_app.logger.exception("Failed to resolve Razorpay plan IDs for webhook; defaulting to monthly")
    return "monthly"


def _plan_amount_paise(plan_type: str) -> int:
    env_var = "RAZORPAY_MONTHLY_PRICE_INR" if plan_type == "monthly" else "RAZORPAY_ANNUAL_PRICE_INR"
    default_rupees = 999 if plan_type == "monthly" else 8999
    raw_value = os.getenv(env_var, str(default_rupees))
    try:
        rupees = float(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive parsing
        raise RuntimeError(f"Invalid value for {env_var}: {raw_value}") from exc
    paise = int(round(rupees * 100))
    if paise <= 0:
        raise RuntimeError(f"{env_var} must be greater than zero")
    return paise


def _plan_period(plan_type: str) -> str:
    return "monthly" if plan_type == "monthly" else "yearly"


@lru_cache(maxsize=2)
def _resolve_plan_id(plan_type: str) -> str:
    client = get_razorpay_client()
    amount_paise = _plan_amount_paise(plan_type)
    period = _plan_period(plan_type)

    # Try to find an existing plan that matches the configured amount.
    plans = client.plan.all({"count": 50}).get("items", [])
    for plan in plans:
        if (
            plan.get("period") == period
            and int(plan.get("interval", 1)) == 1
            and int(plan.get("item", {}).get("amount", 0)) == amount_paise
            and plan.get("item", {}).get("currency") == "INR"
        ):
            return plan.get("id")

    # Create the plan if none exists for the desired amount.
    plan_name = f"Trace Premium {plan_type.title()}"
    plan_description = f"Trace premium subscription billed {plan_type}"
    plan = client.plan.create(
        {
            "period": period,
            "interval": 1,
            "item": {
                "name": plan_name,
                "amount": amount_paise,
                "currency": "INR",
                "description": plan_description,
            },
        }
    )
    plan_id = plan.get("id")
    if not plan_id:
        raise RuntimeError("Failed to create Razorpay plan")
    return plan_id


def handle_webhook_event(event_data: dict) -> None:
    event_type = event_data.get("event")
    payload = event_data.get("payload", {}) if isinstance(event_data, dict) else {}
    subscription_entity = payload.get("subscription", {}).get("entity", {})
    payment_entity = payload.get("payment", {}).get("entity", {})

    subscription_id = subscription_entity.get("id") or payment_entity.get("subscription_id")
    customer_id = subscription_entity.get("customer_id") or payment_entity.get("customer_id")
    user = _find_user(subscription_id, customer_id)
    plan_type = _plan_type_from_event(subscription_entity.get("plan_id"))

    if not user:
        current_app.logger.warning("Webhook received for unknown user: %s", subscription_id)
        return

    if event_type == "subscription.activated":
        activate_premium(user, subscription_id or user.razorpay_subscription_id, plan_type)
    elif event_type == "subscription.charged":
        if user.subscription_expires:
            delta = timedelta(days=31 if plan_type == "monthly" else 366)
            user.subscription_expires = user.subscription_expires + delta
            db.session.commit()
    elif event_type in {"subscription.cancelled", "subscription.completed"}:
        deactivate_premium(user)
    elif event_type == "payment.failed":
        send_payment_failure_email(user)
    else:
        current_app.logger.info("Unhandled Razorpay event: %s", event_type)
