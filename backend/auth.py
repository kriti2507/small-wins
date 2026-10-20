"""Google sign-in and the login_required guard.

Settings are read from the environment when used, not at import, so tests
can flip them with monkeypatch.setenv.
"""
import os
from functools import wraps

from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, current_app, g, jsonify, redirect, request, session, url_for
from joserfc.errors import JoseError

import db
import grants
import storage

DEV_SECRET = "dev-only-not-secret"
GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
# Onboarding tips the frontend may mark as seen (frontend/src/lib/tips.ts).
TIPS = {"starter", "log", "connect"}

bp = Blueprint("auth", __name__)
oauth = OAuth()


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


def current_user_id():
    """Whose data this request may touch, or None.

    The session cookie is signed, so its user_id is trusted as-is. A connected
    MCP app instead sends its grant credential (see grants.py).
    """
    user_id = session.get("user_id")
    if user_id is not None:
        return user_id
    return grants.grant_user_id()


def login_required(fn):
    """Refuse the request unless current_user_id() names someone; routes
    read that id from g.user_id."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = current_user_id()
        if user_id is None:
            return jsonify({"error": "Sign in to continue."}), 401
        g.user_id = user_id
        return fn(*args, **kwargs)

    return wrapper


def check_config(environ, secret_key):
    """Refuse to start with settings that would leave production open."""
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


@bp.route("/api/tips/seen", methods=["POST"])
@grants.session_required  # tips are for the person in the browser
def tips_seen():
    body = request.get_json(silent=True)
    tips = body.get("tips") if isinstance(body, dict) else None
    if (not isinstance(tips, list) or not tips
            or not all(isinstance(t, str) and t in TIPS for t in tips)):
        return jsonify({"error": "Unknown tip."}), 400
    user = db.mark_tips_seen(g.user_id, tips)
    if user is None:
        session.pop("user_id", None)
        return jsonify({"error": "Not signed in."}), 401
    return jsonify({"user": user})


@bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.route("/api/account", methods=["DELETE"])
@grants.session_required  # the person in the browser, never a connected app
def delete_account():
    user_id = g.user_id
    db.delete_user(user_id)
    session.clear()
    # The account is already gone; a failure here only leaves stray images,
    # so it is logged rather than reported.
    try:
        storage.delete_user_objects(user_id)
    except Exception as exc:
        current_app.logger.warning("failed to delete images of user %s: %s", user_id, exc)
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
    # Any Google account may sign in, as long as Google has verified its email.
    if not info.get("email_verified") or not email:
        session.clear()
        return redirect("/login?error=unverified")
    user = db.upsert_user(info["sub"], email, info.get("name"), info.get("picture"))
    return _finish_sign_in(user)
