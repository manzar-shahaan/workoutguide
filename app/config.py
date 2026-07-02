import os
from datetime import timedelta
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
    # Traffic only ever reaches this app over HTTPS (Tailscale terminates TLS
    # in front of it), so the browser-facing cookie can safely require it.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Flask-Login "remember me" cookie: this is what keeps the PWA logged in
    # across launches instead of showing the login form every time. Single-
    # user app sitting behind Tailscale's own device auth, so a long-lived
    # cookie here is a second, low-risk layer rather than the only guard.
    REMEMBER_COOKIE_DURATION = timedelta(days=365)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
