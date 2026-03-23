import io
import zipfile
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, send_file, request
from flask_login import login_required, current_user, logout_user
from sqlalchemy import select

from ..extensions import db
from ..forms.profile_forms import ProfileEditForm, NotificationPreferencesForm, DeleteAccountForm
from ..models.user import User
from ..models.concept import Concept
from ..models.review_event import ReviewEvent
from ..models.connection import ConceptConnection
from ..models.source_item import SourceItem
from ..models.ai_extraction_queue import AIExtractionQueue
from ..models.project import Project
from ..models.application_event import ApplicationEvent
from ..utils.decorators import premium_required
from ..services.data_exporter import export_user_data_as_csv
from ..services.razorpay_service import cancel_subscription
from ..services.email_service import send_account_deletion_email

profile_bp = Blueprint("profile_bp", __name__)


@profile_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    form = ProfileEditForm(obj=current_user)
    stats = {
        "member_since": current_user.created_at,
        "subscription_tier": current_user.subscription_tier,
        "total_concepts": Concept.query.filter_by(user_id=current_user.id).count(),
        "total_reviews": current_user.total_reviews_completed,
        "longest_streak": current_user.longest_streak_days,
    }
    return render_template("profile/settings.html", form=form, stats=stats, active_tab="account")


@profile_bp.route("/profile", methods=["POST"])
@login_required
def update_profile():
    form = ProfileEditForm()
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        db.session.commit()
        flash("Profile updated.", "success")
    else:
        flash("Unable to update profile.", "danger")
    return redirect(url_for("profile_bp.settings_account"))


@profile_bp.route("/settings", methods=["GET"])
@login_required
def settings_root():
    return redirect(url_for("profile_bp.settings_account"))


@profile_bp.route("/settings/account", methods=["GET"])
@login_required
def settings_account():
    form = ProfileEditForm(obj=current_user)
    stats = {
        "member_since": current_user.created_at,
        "subscription_tier": current_user.subscription_tier,
        "total_concepts": Concept.query.filter_by(user_id=current_user.id).count(),
        "total_reviews": current_user.total_reviews_completed,
        "longest_streak": current_user.longest_streak_days,
    }
    return render_template("profile/settings.html", form=form, stats=stats, active_tab="account")


@profile_bp.route("/settings/billing", methods=["GET"])
@login_required
def billing():
    return render_template("profile/billing.html", active_tab="billing")


@profile_bp.route("/settings/notifications", methods=["GET", "POST"])
@login_required
def notifications():
    prefs = current_user.notifications_preferences or {}
    form = NotificationPreferencesForm(obj=current_user)
    if request.method == "GET":
        form.review_reminder_enabled.data = prefs.get("review_reminder_enabled", True)
        form.weekly_report_enabled.data = prefs.get("weekly_report_enabled", True)
        form.application_reminders_enabled.data = prefs.get("application_reminders_enabled", True)
        form.review_reminder_time.data = current_user.review_reminder_time or "08:00"
    if form.validate_on_submit():
        current_user.review_reminder_time = form.review_reminder_time.data
        current_user.notifications_preferences = {
            "review_reminder_enabled": form.review_reminder_enabled.data,
            "weekly_report_enabled": form.weekly_report_enabled.data,
            "application_reminders_enabled": form.application_reminders_enabled.data,
        }
        db.session.commit()
        flash("Notification preferences saved.", "success")
        return redirect(url_for("profile_bp.notifications"))
    return render_template("profile/notifications.html", form=form, active_tab="notifications")


@profile_bp.route("/settings/integrations", methods=["GET"])
@login_required
def integrations():
    return render_template("profile/integrations.html", active_tab="integrations")


@profile_bp.route("/settings/delete-account", methods=["GET", "POST"])
@login_required
def delete_account():
    form = DeleteAccountForm()
    if form.validate_on_submit():
        if current_user.is_premium:
            cancel_subscription(current_user)
        send_account_deletion_email(current_user)

        user_id = current_user.id
        ApplicationEvent.query.filter_by(user_id=user_id).delete()
        ReviewEvent.query.filter_by(user_id=user_id).delete()
        ConceptConnection.query.filter_by(user_id=user_id).delete()
        Concept.query.filter_by(user_id=user_id).delete()
        source_ids = select(SourceItem.id).filter_by(user_id=user_id)
        AIExtractionQueue.query.filter(AIExtractionQueue.source_item_id.in_(source_ids)).delete(synchronize_session=False)
        SourceItem.query.filter_by(user_id=user_id).delete()
        Project.query.filter_by(user_id=user_id).delete()
        User.query.filter_by(id=user_id).delete()
        db.session.commit()
        logout_user()
        flash("Your account has been permanently deleted.", "info")
        return redirect(url_for("main.index"))
    return render_template("profile/delete_account.html", form=form, active_tab="account")


@profile_bp.route("/settings/export", methods=["GET"])
@login_required
@premium_required
def export():
    data = export_user_data_as_csv(current_user)
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, content in data.items():
            zf.writestr(filename, content)
    memory_file.seek(0)
    download_name = f"trace-export-{datetime.utcnow().date().isoformat()}.zip"
    return send_file(memory_file, mimetype="application/zip", as_attachment=True, download_name=download_name)
