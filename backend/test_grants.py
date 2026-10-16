"""MCP grants: the credential a connected app's calls carry, and the routes
that create, redeem, list and revoke grants."""
from datetime import timedelta

import pytest

import app as app_module
import db
from conftest import make_grant, make_user


def sign_bad_ext(c, headers=None):
    # sign_upload rejects .exe with 400 only after login_required passes, so
    # the status says which side of the check we landed on.
    return c.post("/api/uploads/sign", json={"ext": "exe"}, headers=headers or {})


def bearer(credential):
    return {"Authorization": f"Bearer {credential}"}


def grant_row(grant_id):
    with app_module.app.app_context():
        return db.find_grant(grant_id)


def age(grant_id, **columns):
    """Move timestamps into the past, e.g. age(gid, redeemed_at=timedelta(days=31))."""
    with app_module.app.app_context():
        for column, by in columns.items():
            db.get_conn().execute(
                f"update mcp_grants set {column} = now() - %s where id=%s", (by, grant_id))


# --- authenticating with a grant ---------------------------------------------

def test_a_redeemed_grant_acts_as_its_user(db_anon_client):
    me = make_user("sub-me", "me@example.com")
    other = make_user("sub-other", "other@example.com")
    with app_module.app.app_context():
        db.add_topic(other, {"slug": "books", "name": "Books", "color": "red",
                             "layout": "photo-top", "fields": []})
    _, mine = make_grant(me)
    _, theirs = make_grant(other)

    assert sign_bad_ext(db_anon_client, bearer(mine)).status_code == 400
    slugs = lambda cred: [t["slug"] for t in db_anon_client.get("/api/topics", headers=bearer(cred)).get_json()]  # noqa: E731
    assert slugs(mine) == ["runs"]
    assert slugs(theirs) == ["books"]


def test_wrong_secret_unknown_id_and_unredeemed_grants_are_refused(db_anon_client):
    uid = make_user("sub-me", "me@example.com")
    gid, credential = make_grant(uid)
    secret = credential.split(".")[1]
    wrong_secret = credential[:-1] + ("A" if credential[-1] != "A" else "B")
    _, unredeemed = make_grant(uid, redeemed=False)
    for cred in (wrong_secret, f"swg_{gid + 1000}.{secret}", unredeemed):
        res = sign_bad_ext(db_anon_client, bearer(cred))
        assert res.status_code == 401, cred
        assert res.get_json()["error"] == "Sign in to continue."


@pytest.mark.parametrize("header", [
    "swg_1." + "a" * 43,             # no scheme
    "Basic swg_1." + "a" * 43,       # wrong scheme
    "Bearer swg_1." + "a" * 42,      # secret too short
    "Bearer swg_1." + "a" * 44,      # secret too long
    "Bearer swg_0." + "a" * 43,      # ids start at 1
    "Bearer swg_x." + "a" * 43,
    "Bearer swg_1" + "a" * 43,       # no dot
    "Bearer swg_1." + "a" * 42 + "!",
    "Bearer svc-token",
    "Bearer ",
])
def test_malformed_credentials_are_refused_without_a_lookup(anon_client, monkeypatch, header):
    monkeypatch.setattr(db, "find_grant", lambda *a: pytest.fail("looked up a malformed credential"))
    assert sign_bad_ext(anon_client, {"Authorization": header}).status_code == 401


def test_a_grant_unused_for_30_days_stops_working(db_anon_client):
    uid = make_user("sub-me", "me@example.com")
    gid, credential = make_grant(uid)
    age(gid, redeemed_at=timedelta(days=31))
    assert sign_bad_ext(db_anon_client, bearer(credential)).status_code == 401
    age(gid, last_used_at=timedelta(days=29))  # a recent use keeps it alive
    assert sign_bad_ext(db_anon_client, bearer(credential)).status_code == 400


def test_last_used_is_recorded_at_most_hourly(db_anon_client):
    uid = make_user("sub-me", "me@example.com")
    gid, credential = make_grant(uid)
    assert grant_row(gid)["last_used_at"] is None
    sign_bad_ext(db_anon_client, bearer(credential))
    first = grant_row(gid)["last_used_at"]
    assert first is not None
    sign_bad_ext(db_anon_client, bearer(credential))
    assert grant_row(gid)["last_used_at"] == first
    age(gid, last_used_at=timedelta(hours=2))
    old = grant_row(gid)["last_used_at"]
    sign_bad_ext(db_anon_client, bearer(credential))
    assert grant_row(gid)["last_used_at"] > old


def test_service_token_and_acting_user_no_longer_authenticate(db_anon_client, monkeypatch):
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "svc-token")
    uid = make_user("sub-me", "me@example.com")
    res = sign_bad_ext(db_anon_client, {"Authorization": "Bearer svc-token", "X-Acting-User": str(uid)})
    assert res.status_code == 401
