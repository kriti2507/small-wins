"""Google sign-in, the invite allowlist, and the login_required guard.

Settings are read from the environment when used, not at import, so tests
can flip them with monkeypatch.setenv.
"""
import hmac
import os
from functools import wraps

from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, jsonify, redirect, request, session, url_for
from joserfc.errors import JoseError

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
    links to another site. Non-printable characters (tabs, newlines, ...)
    are refused too: browsers strip them before following a link, which can
    turn e.g. "/\\t/evil.com" into "//evil.com" after the checks above ran.
    """
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or not value.isprintable()
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
    if environ.get("VERCEL") and secret_key == DEV_SECRET:
        raise RuntimeError("SECRET_KEY must be set on Vercel")


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


def _finish_sign_in(user):
    next_path = safe_next(session.get("next"))
    session.clear()  # drop Authlib's state and any earlier identity
    session.permanent = True
    session["user_id"] = user["id"]
    return redirect(next_path)


@bp.route("/api/auth/google", methods=["GET"])
def google_login():
    session["next"] = safe_next(request.args.get("next"))
    dev_email = os.environ.get("DEV_LOGIN_EMAIL")
    if dev_email:
        # check_config guarantees this never runs on Vercel.
        return _finish_sign_in(db.upsert_user(f"dev:{dev_email}", dev_email, "Dev", None))
    return oauth.google.authorize_redirect(url_for("auth.google_callback", _external=True))


@bp.route("/api/auth/google/callback", methods=["GET"])
def google_callback():
    try:
        # Exchanges the code and validates the ID token (signature, audience,
        # nonce); "userinfo" holds the verified claims. Expired/clock-skewed
        # or otherwise malformed ID tokens raise joserfc's JoseError here, not
        # OAuthError.
        token = oauth.google.authorize_access_token()
    except (OAuthError, JoseError):
        session.clear()
        return redirect("/login?error=failed")
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").strip().lower()
    if not info.get("email_verified") or not is_allowed(email):
        session.clear()
        return redirect("/login?error=not_invited")
    user = db.upsert_user(info["sub"], email, info.get("name"), info.get("picture"))
    return _finish_sign_in(user)
