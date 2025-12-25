# app/__init__.py
from flask import Flask
from flask_login import LoginManager

from .config import Config


login_manager = LoginManager()


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    # Flask-Login setup
    login_manager.init_app(app)
    login_manager.login_view = "web.login"

    # User loader for Flask-Login
    from .db.connection import get_conn
    from .db.repositories import users as users_repo
    from .web.auth_utils import make_user

    @login_manager.user_loader
    def load_user(user_id: str):
        conn = get_conn()
        try:
            row = users_repo.get_user(conn, int(user_id))
        finally:
            conn.close()
        return make_user(row) if row else None

    # Anti-cache headers so "back after logout" doesn’t show stale pages
    @app.after_request
    def add_no_cache_headers(response):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0, private"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # Register blueprints here
    from .web import web_bp
    app.register_blueprint(web_bp)

    return app
