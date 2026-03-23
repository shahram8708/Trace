from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import func
from ..extensions import db, limiter, mail
from ..forms.auth_forms import RegistrationForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from ..models.user import User
from ..utils.tokens import (
    generate_verification_token,
    confirm_verification_token,
    generate_password_reset_token,
    confirm_password_reset_token,
    SignatureExpired,
    BadSignature,
)
from flask_mail import Message


auth_bp = Blueprint("auth", __name__, url_prefix="")


def send_verification_email(user: User, token: str) -> None:
    verify_url = url_for('auth.verify_email', token=token, _external=True)
    subject = "Verify your Trace account"
    html_body = render_template(
        "auth/email_verification.html",
        user=user,
        verify_url=verify_url,
    )
    text_body = f"Hello {user.get_display_name()},\n\nPlease verify your Trace account by visiting {verify_url}. This link expires in 24 hours."
    msg = Message(subject=subject, recipients=[user.email], html=html_body, body=text_body)
    try:
        mail.send(msg)
    except Exception:
        current_app.logger.exception("Error sending verification email")


def send_password_reset_email(user: User, token: str) -> None:
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    subject = "Reset your Trace password"
    html_body = render_template(
        "auth/email_password_reset.html",
        user=user,
        reset_url=reset_url,
    )
    text_body = (
        f"Hello {user.get_display_name()},\n\nUse the link to reset your password: {reset_url}. "
        "If you didn't request this, you can ignore this email."
    )
    msg = Message(subject=subject, recipients=[user.email], html=html_body, body=text_body)
    try:
        mail.send(msg)
    except Exception:
        current_app.logger.exception("Error sending password reset email")


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard_bp.dashboard"))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed = generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=16)
        user = User(
            email=form.email.data.lower(),
            password_hash=hashed,
            first_name=form.first_name.data,
            is_verified=False,
            onboarding_complete=False,
            subscription_tier="free",
        )
        db.session.add(user)
        db.session.commit()
        token = generate_verification_token(user.email)
        send_verification_email(user, token)
        flash("Account created! Please check your email to verify your account.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/signup.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard_bp.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            db.select(User).filter(func.lower(User.email) == form.email.data.lower())
        ).scalar_one_or_none()
        if not user or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)
        if not user.is_verified:
            flash("Please verify your email before logging in.", "warning")
            return redirect(url_for("auth.verify_pending"))
        remember_duration = current_app.config.get("REMEMBER_COOKIE_DURATION", timedelta(days=365))
        login_user(user, remember=True, duration=remember_duration)
        session.permanent = True
        user.last_login = datetime.utcnow()
        db.session.commit()
        next_url = request.args.get("next")
        return redirect(next_url or url_for("dashboard_bp.dashboard"))
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/verify/<token>")
def verify_email(token):
    try:
        email = confirm_verification_token(token)
    except (SignatureExpired, BadSignature):
        flash("Verification link is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for("auth.verify_pending"))
    user = db.session.execute(db.select(User).filter(User.email == email)).scalar_one_or_none()
    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.signup"))
    if user.is_verified:
        flash("Email already verified. Please log in.", "info")
        return redirect(url_for("auth.login"))
    user.is_verified = True
    db.session.commit()
    flash("Email verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/verify-pending")
def verify_pending():
    email = current_user.email if current_user.is_authenticated else None
    return render_template("auth/verify_pending.html", email=email)


@auth_bp.route("/resend-verification", methods=["POST"])
@limiter.limit("3 per hour")
def resend_verification():
    email = None
    if current_user.is_authenticated and not current_user.is_verified:
        email = current_user.email
    if not email:
        email = request.form.get("email")
    user = db.session.execute(db.select(User).filter(User.email == (email or ""))).scalar_one_or_none()
    if user and not user.is_verified:
        token = generate_verification_token(user.email)
        send_verification_email(user, token)
        flash("Verification email resent.", "success")
    else:
        flash("If an account exists, a verification email has been sent.", "info")
    return redirect(url_for("auth.verify_pending"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).filter(User.email == form.email.data.lower())).scalar_one_or_none()
        if user and user.is_verified:
            token = generate_password_reset_token(user.email)
            send_password_reset_email(user, token)
        flash("If an account exists with that email, a password reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset/<token>", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def reset_password(token):
    try:
        email = confirm_password_reset_token(token)
    except (SignatureExpired, BadSignature):
        flash("Reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))
    user = db.session.execute(db.select(User).filter(User.email == email)).scalar_one_or_none()
    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.signup"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password_hash = generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=16)
        db.session.commit()
        flash("Password updated successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)
