import logging
import os
import sys
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv


env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path, override=False)


class Config:
    # Provide a safe default for local/dev runs; require explicit value in production
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    if not os.getenv("SECRET_KEY") and os.getenv("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in production")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///trace_dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True

    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "0")) if os.getenv("MAIL_PORT") else None
    MAIL_USE_TLS = bool(int(os.getenv("MAIL_USE_TLS", "0"))) if os.getenv("MAIL_USE_TLS") else False
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    RATELIMIT_DEFAULT = "200 per day;50 per hour"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Keep users signed in for a year unless they explicitly log out
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)
    REMEMBER_COOKIE_DURATION = timedelta(days=365)
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST = False

    # Celery defaults: assume Redis in prod, override in env/config per environment
    CELERY_BROKER_URL = os.getenv("REDIS_URL")
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL")
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = True


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    # Run tasks inline with an in-memory broker so Redis is not required locally
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    CONTENT_SECURITY_POLICY = {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
        "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
        "img-src": "'self' data:",
        "font-src": "'self' data:",
        "connect-src": "'self'",
    }

    @classmethod
    def validate(cls):
        # Require explicit Redis configuration in production
        if not cls.CELERY_BROKER_URL or not cls.CELERY_RESULT_BACKEND:
            raise RuntimeError("REDIS_URL must be set in production for Celery")


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def configure_logging(app):
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.addHandler(console_handler)

    app.logger.setLevel(log_level)

    genai_logger = logging.getLogger("google")
    genai_logger.setLevel(logging.WARNING)

    print(f"[LOGGING] Configured at level: {logging.getLevelName(log_level)}")
