"""MCP grants: the credential a connected app's calls carry, and the routes
that create, redeem, list and revoke grants."""
import hashlib
import re
from datetime import datetime, timedelta

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


# --- routes ------------------------------------------------------------------

def me_id(c):
    return c.get("/api/auth/me").get_json()["user"]["id"]


def create(c, **body):
    return c.post("/api/mcp/grants", json={"client_name": "Claude", "redirect_host": "claude.ai", **body})


def grant_id_of(credential):
    return int(credential.removeprefix("swg_").split(".")[0])


def test_a_created_grant_works_once_redeemed(client):
    res = create(client)
    assert res.status_code == 201
    credential = res.get_json()["credential"]
    assert re.fullmatch(r"swg_[1-9][0-9]*\.[A-Za-z0-9_-]{43}", credential)

    app_client = app_module.app.test_client()  # no session: just the credential
    assert sign_bad_ext(app_client, bearer(credential)).status_code == 401
    assert app_client.post("/api/mcp/grants/redeem", headers=bearer(credential)).status_code == 200
    assert sign_bad_ext(app_client, bearer(credential)).status_code == 400


def test_only_a_hash_of_the_secret_is_stored(client):
    credential = create(client).get_json()["credential"]
    row = grant_row(grant_id_of(credential))
    secret = credential.split(".")[1]
    assert row["secret_hash"] == hashlib.sha256(secret.encode()).hexdigest()
    assert secret not in str(row)
    assert (row["user_id"], row["client_name"], row["redirect_host"]) == (me_id(client), "Claude", "claude.ai")


def test_client_name_is_optional_and_text_is_trimmed(client):
    res = client.post("/api/mcp/grants", json={"redirect_host": "  claude.ai  "})
    row = grant_row(grant_id_of(res.get_json()["credential"]))
    assert (row["client_name"], row["redirect_host"]) == (None, "claude.ai")


@pytest.mark.parametrize("body", [{}, {"redirect_host": ""}, {"redirect_host": "   "}, {"redirect_host": 5}, []])
def test_create_needs_a_redirect_host(client, body):
    res = client.post("/api/mcp/grants", json=body)
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_grant_management_needs_a_session_not_a_grant(db_anon_client):
    gid, credential = make_grant(make_user("sub-me", "me@example.com"))
    for method, path in [("POST", "/api/mcp/grants"), ("GET", "/api/mcp/grants"),
                         ("DELETE", f"/api/mcp/grants/{gid}")]:
        res = db_anon_client.open(path, method=method, json={"redirect_host": "x"}, headers=bearer(credential))
        assert res.status_code == 401, f"{method} {path}"
    assert grant_row(gid) is not None


def test_redeeming_twice_kills_the_grant(db_anon_client):
    gid, credential = make_grant(make_user("sub-me", "me@example.com"), redeemed=False)
    assert db_anon_client.post("/api/mcp/grants/redeem", headers=bearer(credential)).status_code == 200
    res = db_anon_client.post("/api/mcp/grants/redeem", headers=bearer(credential))
    assert res.status_code == 409
    assert grant_row(gid) is None
    assert sign_bad_ext(db_anon_client, bearer(credential)).status_code == 401


def test_redeem_needs_the_grant_credential(client):
    _, credential = make_grant(me_id(client), redeemed=False)
    assert client.post("/api/mcp/grants/redeem").status_code == 401  # a session isn't enough
    wrong = credential[:-1] + ("A" if credential[-1] != "A" else "B")
    assert client.post("/api/mcp/grants/redeem", headers=bearer(wrong)).status_code == 401


def test_self_says_whether_the_grant_still_works(client):
    gid, credential = make_grant(me_id(client))
    app_client = app_module.app.test_client()
    res = app_client.get("/api/mcp/grants/self", headers=bearer(credential))
    assert res.status_code == 200
    assert res.get_json() == {"id": gid}
    assert grant_row(gid)["last_used_at"] is None  # a check isn't a use

    assert client.get("/api/mcp/grants/self").status_code == 401  # session doesn't count
    age(gid, redeemed_at=timedelta(days=31))
    assert app_client.get("/api/mcp/grants/self", headers=bearer(credential)).status_code == 401

    _, unredeemed = make_grant(me_id(client), redeemed=False)
    assert app_client.get("/api/mcp/grants/self", headers=bearer(unredeemed)).status_code == 401


def test_list_shows_own_redeemed_grants_newest_first(client, second_client):
    mine = me_id(client)
    older, _ = make_grant(mine)
    newer, _ = make_grant(mine)
    make_grant(mine, redeemed=False)
    make_grant(me_id(second_client))
    age(older, created_at=timedelta(days=2))

    res = client.get("/api/mcp/grants")
    assert res.status_code == 200
    listed = res.get_json()
    assert [g["id"] for g in listed] == [newer, older]
    assert listed[0] == {"id": newer, "client_name": "Claude", "redirect_host": "claude.ai",
                         "created_at": listed[0]["created_at"], "last_used_at": None}
    datetime.fromisoformat(listed[0]["created_at"])


def test_last_used_is_listed_once_the_app_calls(client):
    gid, credential = make_grant(me_id(client))
    sign_bad_ext(app_module.app.test_client(), bearer(credential))
    [listed] = client.get("/api/mcp/grants").get_json()
    datetime.fromisoformat(listed["last_used_at"])


def test_revoking_cuts_the_app_off(client):
    gid, credential = make_grant(me_id(client))
    app_client = app_module.app.test_client()
    assert sign_bad_ext(app_client, bearer(credential)).status_code == 400

    res = client.delete(f"/api/mcp/grants/{gid}")
    assert res.status_code == 204
    assert sign_bad_ext(app_client, bearer(credential)).status_code == 401
    assert client.get("/api/mcp/grants").get_json() == []
    assert client.delete(f"/api/mcp/grants/{gid}").status_code == 404


def test_cannot_revoke_another_users_grant(client, second_client):
    gid, _ = make_grant(me_id(second_client))
    res = client.delete(f"/api/mcp/grants/{gid}")
    assert res.status_code == 404
    assert grant_row(gid) is not None
    assert client.delete("/api/mcp/grants/999999").status_code == 404
