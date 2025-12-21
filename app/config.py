import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # project/app/.. = project root


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://workoutguide:workoutguide@localhost:5432/workoutguide",
    )
    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True       # JS can't read the cookie
    SESSION_COOKIE_SECURE = False        # True in production behind HTTPS
    SESSION_COOKIE_SAMESITE = "Lax"      # Good default to mitigate CSRF

    # If you want to be explicit about permanent sessions:
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 days, for example
