# app/web/__init__.py

from flask import Blueprint
from flask_login import current_user

from .auth_utils import sync_g_user

# 1) Define the blueprint first
web_bp = Blueprint(
    "web",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# 2) Then import routes so they can `from .. import web_bp`
from .routes import workouts  # noqa: E402,F401
from .routes import auth      # noqa: E402,F401
from .routes import exercises # noqa: E402,F401


@web_bp.before_app_request
def load_logged_in_user():
    """
    Keep g.user in sync with Flask-Login's current_user
    so templates/routes can continue using g.user.
    """
    sync_g_user()


@web_bp.app_context_processor
def inject_current_user():
    """
    Make `current_user` available in all templates
    (Flask-Login also does this, but this keeps your old pattern explicit).
    """
    return {"current_user": current_user}
