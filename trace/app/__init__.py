import os
from datetime import datetime, timedelta, date
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template
from markupsafe import Markup
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix
try:
    import google.genai as genai
except Exception:  # pragma: no cover
    genai = None
from sqlalchemy import func
from .extensions import db, migrate, login_manager, mail, limiter, cache, csrf
from .routes.main import main_bp
from .routes.auth import auth_bp
from .routes.onboarding import onboarding_bp
from .routes.import_bp import import_bp
from .routes.review import review_bp
from .routes.dashboard import dashboard_bp
from .routes.concepts import concepts_bp
from .routes.library import library_bp
from .routes.map import map_bp
from .routes.projects import projects_bp
from .routes.reports import reports_bp
from .routes.billing import billing_bp
from .routes.profile import profile_bp
from .routes.admin import admin_bp
from .utils.free_tier import check_free_tier_limits
from .utils.markdown_renderer import (
    convert_markdown,
    convert_markdown_with_toc,
    is_markdown,
    markdown_to_safe_html,
)
from .models.concept import Concept
from .models.application_event import ApplicationEvent
from .models import *  # noqa: F401,F403


env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path, override=False)

from .config import DevelopmentConfig, ProductionConfig, configure_logging


def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.config.from_object(config_class)
    app.permanent_session_lifetime = getattr(config_class, "PERMANENT_SESSION_LIFETIME", timedelta(minutes=90))

    # Validate critical production settings early
    if config_class is ProductionConfig:
        ProductionConfig.validate()

    configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    csrf.init_app(app)

    from celery_worker import create_celery_app, celery as celery_app

    create_celery_app(app)
    app.celery = celery_app

    if genai:
        api_key = app.config.get("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

    register_filters(app)
    register_error_handlers(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(concepts_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(admin_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from .models.user import User
        return db.session.get(User, int(user_id)) if user_id else None

    @app.context_processor
    def inject_dashboard_nav():
        if not current_user.is_authenticated:
            return {}

        today = date.today()
        due_count = db.session.scalar(
            db.select(func.count(Concept.id)).filter(
                Concept.user_id == current_user.id,
                Concept.is_active.is_(True),
                Concept.next_review_due <= today,
            )
        ) or 0

        pending_application_prompts = db.session.scalar(
            db.select(func.count(ApplicationEvent.id)).filter(
                ApplicationEvent.user_id == current_user.id,
                ApplicationEvent.user_response.is_(None),
            )
        ) or 0

        limits = check_free_tier_limits(current_user)

        return {
            "nav_due_count": int(due_count),
            "nav_limits": limits,
            "pending_application_prompts_count": int(pending_application_prompts),
        }

    @app.context_processor
    def inject_markdown_flag():
        return {"markdown_enabled": True}

    return app


def register_filters(app):
    @app.template_filter("time_ago")
    def time_ago(value):
        if not value:
            return "just now"
        now = datetime.utcnow()
        delta = now - value if isinstance(value, datetime) else timedelta()
        seconds = int(delta.total_seconds())
        intervals = (
            (31536000, "year"),
            (2592000, "month"),
            (604800, "week"),
            (86400, "day"),
            (3600, "hour"),
            (60, "minute"),
            (1, "second"),
        )
        for count, name in intervals:
            amount = seconds // count
            if amount:
                suffix = "s" if amount > 1 else ""
                return f"{amount} {name}{suffix} ago"
        return "just now"

    @app.template_filter("retention_color")
    def retention_color(value):
        try:
            score = float(value)
        except (TypeError, ValueError):
            return "secondary"
        if score >= 0.8:
            return "success"
        if score >= 0.5:
            return "warning"
        return "danger"

    @app.template_filter("format_inr")
    def format_inr(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "₹0"
        return f"₹{number:,.0f}"

    @app.template_filter("markdown")
    def markdown_filter(value):
        return Markup(convert_markdown(value))

    @app.template_filter("markdown_safe")
    def markdown_safe_filter(value):
        return Markup(markdown_to_safe_html(value))

    @app.template_filter("is_markdown")
    def is_markdown_filter(value):
        return is_markdown(value)

    app.jinja_env.globals["render_markdown"] = convert_markdown
    app.jinja_env.globals["convert_markdown_with_toc"] = convert_markdown_with_toc
    app.jinja_env.globals["markdown_to_safe_html"] = markdown_to_safe_html


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("errors/500.html"), 500

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403
