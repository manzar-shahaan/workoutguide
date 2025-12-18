# app/web/auth_utils.py
from functools import wraps

from flask import g
from flask_login import (
    current_user,
    login_required as flask_login_required,
    UserMixin,
)


class User(UserMixin):
    """
    Lightweight user wrapper for Flask-Login, built from a sqlite3.Row.
    """

    def __init__(self, row):
        # sqlite3.Row supports dict-style access and .keys(), but not .get()
        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]

        keys = row.keys()

        if "weight_unit" in keys and row["weight_unit"] is not None:
            self.weight_unit = row["weight_unit"]
        else:
            self.weight_unit = "lb"

        if "recovery_email" in keys:
            self.recovery_email = row["recovery_email"]
        else:
            self.recovery_email = None

        if "totp_enabled" in keys:
            self.totp_enabled = row["totp_enabled"]
        else:
            self.totp_enabled = 0

        if "totp_secret" in keys:
            self.totp_secret = row["totp_secret"]
        else:
            self.totp_secret = None


def make_user(row):
    """Construct a Flask-Login user object from a DB row."""
    if row is None:
        return None
    return User(row)


def sync_g_user():
    """
    Keep g.user in sync with the Flask-Login current_user.
    Your templates already expect g.user, so we keep that API.
    """
    if current_user.is_authenticated:
        g.user = {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "weight_unit": getattr(current_user, "weight_unit", "lb"),
            "recovery_email": getattr(current_user, "recovery_email", None),
        }
    else:
        g.user = None


def login_required(view):
    """
    Drop-in replacement for your old @login_required that leverages Flask-Login
    but still makes sure g.user is populated.
    """

    @wraps(view)
    @flask_login_required
    def wrapped_view(*args, **kwargs):
        sync_g_user()
        return view(*args, **kwargs)

    return wrapped_view
