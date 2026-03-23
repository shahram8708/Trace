import os
from pathlib import Path
from dotenv import load_dotenv
from flask_migrate import upgrade
from trace.app import create_app
from trace.app.config import DevelopmentConfig
from trace.app.extensions import db


env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, override=False)


def main():
    app = create_app(DevelopmentConfig)
    with app.app_context():
        migrations_path = os.path.join(os.path.dirname(__file__), "migrations")
        if os.path.isdir(migrations_path):
            try:
                upgrade()  # apply migrations; creates DB if it doesn't exist
            except Exception:
                db.create_all()  # fallback if migrations are broken
        else:
            db.create_all()  # fresh setup without migrations folder

    debug = bool(int(os.getenv("FLASK_DEBUG", "0")))
    app.run(host="0.0.0.0", port=5000, debug=debug, use_reloader=False)


if __name__ == "__main__":
    main()
