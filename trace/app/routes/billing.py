import json
import os

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from ..extensions import csrf
from ..services.razorpay_service import (
    create_subscription,
    verify_payment_signature,
    activate_premium,
    verify_webhook_signature,
    handle_webhook_event,
    cancel_subscription,
    is_captured_payment_for_subscription,
    reactivate_subscription,
)
from ..services.email_service import send_subscription_cancellation_email
from ..utils.decorators import premium_required

billing_bp = Blueprint("billing_bp", __name__, url_prefix="/billing")


@billing_bp.route("/create-order", methods=["POST"])
@login_required
def create_order():
    payload = request.get_json() or {}
    plan_type = payload.get("plan_type")
    if plan_type not in {"monthly", "annual"}:
        return jsonify({"success": False, "error": "Invalid plan"}), 400
    if not current_user.is_verified:
        return jsonify({"success": False, "error": "Verify your email before upgrading."}), 400
    try:
        subscription = create_subscription(current_user, plan_type)
        return jsonify(
            {
                "success": True,
                "key_id": os.getenv("RAZORPAY_KEY_ID"),
                "subscription_id": subscription.get("id"),
            }
        )
    except Exception:
        return jsonify({"success": False, "error": "Payment system temporarily unavailable. Please try again."}), 503


@billing_bp.route("/verify-payment", methods=["POST"])
@login_required
def verify_payment():
    payload = request.get_json() or {}
    payment_id = payload.get("razorpay_payment_id")
    subscription_id = payload.get("razorpay_subscription_id")
    signature = payload.get("razorpay_signature")
    plan_type = payload.get("plan_type", "monthly")

    if not all([payment_id, subscription_id, signature]):
        current_app.logger.warning(
            "Razorpay verify-payment missing fields", extra={"payment_id": payment_id, "subscription_id": subscription_id}
        )
        return jsonify({"success": False, "error": "Missing payment details."}), 400

    signature_ok = verify_payment_signature(payment_id, subscription_id, signature)
    if not signature_ok:
        # Fallback: fetch payment server-side to validate status and subscription match
        try:
            payment_ok, seen_sub_id = is_captured_payment_for_subscription(payment_id, subscription_id)
            signature_ok = payment_ok
            if payment_ok and seen_sub_id and not subscription_id:
                subscription_id = seen_sub_id
        except Exception as exc:
            current_app.logger.exception("Razorpay payment fetch/verify failed: %s", exc)

    if not signature_ok:
        current_app.logger.warning(
            "Razorpay verification failed", extra={"payment_id": payment_id, "subscription_id": subscription_id}
        )
        return jsonify({"success": False, "error": "Payment verification failed."}), 400

    activate_premium(current_user, subscription_id, plan_type)
    return jsonify({"success": True, "message": "Subscription activated! Welcome to Trace Pro."})


@billing_bp.route("/webhook", methods=["POST"])
@csrf.exempt
def webhook():
    raw_body = request.get_data() or b""
    signature = request.headers.get("razorpay-signature")
    if not signature or not verify_webhook_signature(raw_body, signature):
        return jsonify({"error": "Invalid signature"}), 400
    try:
        event_data = request.get_json(force=True, silent=True) or {}
        handle_webhook_event(event_data)
    except Exception:
        pass
    return jsonify({"status": "ok"}), 200


@billing_bp.route("/success", methods=["GET"])
@login_required
def success():
    flash("Your subscription is active!", "success")
    return render_template("profile/billing.html")


@billing_bp.route("/failure", methods=["GET"])
@login_required
def failure():
    flash("Payment failed. Please try again or contact support.", "danger")
    return render_template("profile/billing.html")


@billing_bp.route("/cancel", methods=["POST"])
@login_required
@premium_required
def cancel():
    cancelled = cancel_subscription(current_user)
    if cancelled:
        send_subscription_cancellation_email(current_user)
        flash("Your subscription has been cancelled. You'll no longer be charged and access has been revoked.", "info")
    else:
        flash("We couldn't cancel your subscription. Please try again or contact support.", "danger")
    return redirect(url_for("profile_bp.billing"))


@billing_bp.route("/reactivate", methods=["POST"])
@login_required
def reactivate():
    if current_user.is_premium:
        flash("Your subscription is already active.", "info")
        return redirect(url_for("profile_bp.billing"))

    if not current_user.subscription_cancel_at and not current_user.razorpay_subscription_id:
        flash("No cancelled subscription found to restart.", "warning")
        return redirect(url_for("profile_bp.billing"))

    try:
        plan_type = current_user.subscription_tier if current_user.subscription_tier in {"monthly", "annual"} else "monthly"
        reactivate_subscription(current_user, plan_type)
        flash("Subscription restarted. Welcome back to Trace Pro!", "success")
    except Exception:
        flash("We couldn't restart your subscription right now. Please try again or contact support.", "danger")
    return redirect(url_for("profile_bp.billing"))
