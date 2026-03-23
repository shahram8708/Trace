import os
from pathlib import Path
from dotenv import load_dotenv
from celery import Celery
from celery.schedules import crontab
from werkzeug.utils import import_string

celery = Celery("trace")

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, override=False)


def create_celery_app(flask_app):
    broker_url = flask_app.config.get("CELERY_BROKER_URL") or os.getenv(
        "REDIS_URL", "redis://localhost:6379/0"
    )
    result_backend = flask_app.config.get("CELERY_RESULT_BACKEND") or broker_url
    task_always_eager = flask_app.config.get("CELERY_TASK_ALWAYS_EAGER", False)
    task_eager_propagates = flask_app.config.get("CELERY_TASK_EAGER_PROPAGATES", True)

    celery.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_always_eager=task_always_eager,
        task_eager_propagates=task_eager_propagates,
        broker_connection_retry_on_startup=not task_always_eager,
        beat_schedule={
            "weekly-reports": {
                "task": "trace.app.tasks.send_weekly_reports_to_all_users",
                "schedule": crontab(hour=8, minute=0, day_of_week=1),
            },
            "hourly-review-reminders": {
                "task": "trace.app.tasks.send_review_reminders",
                "schedule": crontab(minute=0),
            },
            "nightly-retention-update": {
                "task": "trace.app.tasks.update_all_retention_scores",
                "schedule": crontab(hour=2, minute=0),
            },
            "connection-suggestions": {
                "task": "trace.app.tasks.generate_connection_suggestions_all_users",
                "schedule": crontab(minute=0, hour="*/6"),
            },
        },
        imports=("trace.app.tasks",),
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return super().__call__(*args, **kwargs)

    celery.Task = ContextTask
    return celery


# Configure Celery when running workers directly
if os.getenv("FLASK_SKIP_CELERY_INIT") != "1":
    try:
        from trace.app import create_app

        config_path = os.getenv("FLASK_CONFIG", "trace.app.config.ProductionConfig")
        try:
            config_class = import_string(config_path)
        except Exception:
            from trace.app.config import DevelopmentConfig

            config_class = DevelopmentConfig

        flask_app = create_app(config_class=config_class)
        create_celery_app(flask_app)
        celery.flask_app = flask_app
    except Exception:  # pragma: no cover - defensive initialization for worker startup
        pass
