from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user


def premium_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_premium:
            flash("Upgrade to access this feature.", "warning")
            return redirect(url_for("main.pricing"))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def verified_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_verified:
            flash("Please verify your email to continue.", "warning")
            return redirect(url_for("auth.verify_pending"))
        return fn(*args, **kwargs)

    return wrapper


def onboarding_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.onboarding_complete:
            flash("Finish onboarding to access your dashboard.", "info")
            return redirect(url_for("onboarding.step1"))
        return fn(*args, **kwargs)

    return wrapper
