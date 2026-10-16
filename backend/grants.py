"""MCP grants: one stored, revocable credential per connected app.

Connecting an app (the MCP server's consent page) creates a grant for the
signed-in user and hands the MCP server a credential, `swg_<id>.<secret>`,
which it sends back as `Authorization: Bearer ...` on every API call. Only a
sha256 of the secret is stored. Revoking an app deletes its row, so its next
call fails.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, g, jsonify, request, session

import db

# The id must fit a Postgres bigint; token_urlsafe(32) is always 43 characters.
CREDENTIAL_RE = re.compile(r"swg_([1-9][0-9]{0,17})\.([A-Za-z0-9_-]{43})")
# A connection unused this long stops working (refresh tokens last 30 days
# too, so an app in regular use never hits it).
STALE_AFTER = timedelta(days=30)

MAX_NAME = 200
MAX_HOST = 500

bp = Blueprint("grants", __name__)


def hash_secret(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def mint(user_id, client_name, redirect_host):
    """Create an unredeemed grant and return its credential. This is the only
    time the secret exists outside the MCP server's tokens."""
    secret = secrets.token_urlsafe(32)
    grant_id = db.create_grant(user_id, client_name, redirect_host, hash_secret(secret))
    return f"swg_{grant_id}.{secret}"


def presented_grant():
    """The grant whose credential this request carries (redeemed or not), or
    None. Malformed credentials are refused before any query."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    match = CREDENTIAL_RE.fullmatch(token) if scheme.lower() == "bearer" else None
    if not match:
        return None
    grant = db.find_grant(int(match.group(1)))
    if grant is None or not hmac.compare_digest(hash_secret(match.group(2)), grant["secret_hash"]):
        return None
    return grant


def usable(grant):
    """Redeemed, and used (or redeemed) within STALE_AFTER."""
    if grant is None or grant["redeemed_at"] is None:
        return False
    last = grant["last_used_at"] or grant["redeemed_at"]
    return datetime.now(timezone.utc) - last <= STALE_AFTER


def grant_user_id():
    """The user a usable grant credential on this request acts for, or None."""
    grant = presented_grant()
    if not usable(grant):
        return None
    db.touch_grant(grant["id"])
    return grant["user_id"]


# --- routes ------------------------------------------------------------------

def session_required(fn):
    """For the person in the browser only: a connected app (a grant
    credential) must not create, list or revoke grants."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            return jsonify({"error": "Sign in to continue."}), 401
        g.user_id = user_id
        return fn(*args, **kwargs)

    return wrapper


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _public(grant):
    last = grant["last_used_at"]
    return {
        "id": grant["id"],
        "client_name": grant["client_name"],
        "redirect_host": grant["redirect_host"],
        "created_at": grant["created_at"].isoformat(),
        "last_used_at": last.isoformat() if last else None,
    }


@bp.route("/api/mcp/grants", methods=["POST"])
@session_required
def create_grant():
    """Called by the MCP consent page on Allow, with the browser's cookie."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    redirect_host = _text(data.get("redirect_host"), MAX_HOST)
    if not redirect_host:
        return jsonify({"error": "redirect_host is required."}), 400
    client_name = _text(data.get("client_name"), MAX_NAME) or None
    return jsonify({"credential": mint(g.user_id, client_name, redirect_host)}), 201


@bp.route("/api/mcp/grants", methods=["GET"])
@session_required
def list_grants():
    return jsonify([_public(grant) for grant in db.list_grants(g.user_id)])


@bp.route("/api/mcp/grants/<int:grant_id>", methods=["DELETE"])
@session_required
def revoke_grant(grant_id):
    if not db.delete_grant(g.user_id, grant_id):
        return jsonify({"error": "Not found."}), 404
    return "", 204


@bp.route("/api/mcp/grants/redeem", methods=["POST"])
def redeem_grant():
    """Called once, when the app exchanges its authorization code. A second
    redeem means the code was replayed, so the grant is killed: neither the
    app nor whoever replayed the code can use it."""
    grant = presented_grant()
    if grant is None:
        return jsonify({"error": "Unknown grant."}), 401
    if db.redeem_grant(grant["id"]):
        return jsonify({"ok": True})
    db.delete_grant(grant["user_id"], grant["id"])
    return jsonify({"error": "This connection was already used."}), 409


@bp.route("/api/mcp/grants/self", methods=["GET"])
def check_grant():
    """Lets the MCP server ask, before refreshing a token, whether the grant
    still works. Not a use, so last_used_at is left alone."""
    grant = presented_grant()
    if not usable(grant):
        return jsonify({"error": "Unknown grant."}), 401
    return jsonify({"id": grant["id"]})
