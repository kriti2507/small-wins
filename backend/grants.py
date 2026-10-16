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

from flask import request

import db

# The id must fit a Postgres bigint; token_urlsafe(32) is always 43 characters.
CREDENTIAL_RE = re.compile(r"swg_([1-9][0-9]{0,17})\.([A-Za-z0-9_-]{43})")
# A connection unused this long stops working (refresh tokens last 30 days
# too, so an app in regular use never hits it).
STALE_AFTER = timedelta(days=30)


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
