"""Google sign-in, the invite allowlist, and the login_required guard.

Settings are read from the environment when used, not at import, so tests
can flip them with monkeypatch.setenv.
"""
import hmac
import os
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, jsonify, request, session

import db

DEV_SECRET = "dev-only-not-secret"
GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"

bp = Blueprint("auth", __name__)
oauth = OAuth()


def is_allowed(email):
    """The one place that decides who may sign in. To open signup to any
    Google account later, change only this function."""
    allowed = {
        e.strip().lower()
        for e in os.environ.get("ALLOWED_EMAILS", "").split(",")
        if e.strip()
    }
    return bool(email) and email.strip().lower() in allowed


def safe_next(value):
    """A path on this site to return to after sign-in; anything else is '/'.

    '//host' and backslashes are refused because browsers treat both as
    links to another site.
    """
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
    ):
        return "/"
    return value


def has_service_token():
    """The MCP server's bearer token. Phase 1 only: Phase 3 replaces it with
    a per-user identity."""
    expected = os.environ.get("MCP_SERVICE_TOKEN")
    if not expected:
        return False
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return scheme.lower() == "bearer" and hmac.compare_digest(token.encode(), expected.encode())


def login_required(fn):
    """Signed in (the session cookie is signed, so its user_id is trusted)
    or the MCP service token."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("user_id") is None and not has_service_token():
            return jsonify({"error": "Sign in to continue."}), 401
        return fn(*args, **kwargs)

    return wrapper


def check_config(environ, secret_key):
    """Refuse to start with settings that would leave production open."""
    if environ.get("DEV_LOGIN_EMAIL") and environ.get("VERCEL"):
        raise RuntimeError("DEV_LOGIN_EMAIL must never be set on Vercel")
    if environ.get("GOOGLE_CLIENT_ID") and secret_key == DEV_SECRET:
        raise RuntimeError("SECRET_KEY must be set when Google sign-in is configured")


def init_app(app):
    oauth.init_app(app)
    oauth.register(
        "google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url=GOOGLE_METADATA_URL,
        client_kwargs={"scope": "openid email profile"},
    )
    app.register_blueprint(bp)


@bp.route("/api/auth/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    user = db.find_user(user_id) if user_id is not None else None
    if user is None:
        session.pop("user_id", None)
        return jsonify({"error": "Not signed in."}), 401
    return jsonify({"user": user})


@bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})
