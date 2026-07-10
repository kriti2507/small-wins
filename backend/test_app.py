import pytest
from werkzeug.security import generate_password_hash

import app as app_module

TEST_PASSWORD = "correct horse"
TEST_HASH = generate_password_hash(TEST_PASSWORD, method="pbkdf2:sha256")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point all file IO at a throwaway dir; module globals are read at call
    # time, so monkeypatching them is enough.
    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "TOPICS_FILE", str(tmp_path / "topics.json"))
    monkeypatch.setattr(app_module, "UPLOADS_DIR", str(tmp_path / "uploads"))
    # Dev mode: no password configured, every request is admin.
    # raising=False lets this fixture run before the attributes exist (red
    # phase of TDD) without breaking the pre-existing tests.
    monkeypatch.setattr(app_module, "ADMIN_PASSWORD_HASH", None, raising=False)
    monkeypatch.setattr(app_module, "LOGIN_ATTEMPTS", {}, raising=False)
    app_module.app.config["TESTING"] = True
    app_module.app.config["SESSION_COOKIE_SECURE"] = False
    return app_module.app.test_client()


@pytest.fixture()
def auth_client(client, monkeypatch):
    # Same client, but with an admin password configured (production mode).
    monkeypatch.setattr(app_module, "ADMIN_PASSWORD_HASH", TEST_HASH)
    return client


def log_in(c, password=TEST_PASSWORD):
    return c.post("/api/auth/login", json={"password": password})


DOC = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "hi"}]},
        {"type": "figure", "attrs": {"src": "/api/uploads/a.jpg", "width": "wide"},
         "content": [{"type": "text", "text": "a caption"}]},
    ],
}


def make_entry(client):
    # The app seeds a default "runs" topic on first read.
    res = client.post("/api/topics/runs/entries", json={"date": "2026-07-09", "title": "Run"})
    assert res.status_code == 201
    return res.get_json()["id"]


def test_patch_body_round_trip(client):
    entry_id = make_entry(client)
    res = client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    assert res.status_code == 200
    res = client.get(f"/api/topics/runs/entries/{entry_id}")
    assert res.get_json()["body"] == DOC


def test_patch_accepts_empty_doc(client):
    entry_id = make_entry(client)
    res = client.patch(
        f"/api/topics/runs/entries/{entry_id}",
        json={"body": {"type": "doc", "content": []}},
    )
    assert res.status_code == 200


def test_patch_rejects_non_doc_bodies(client):
    entry_id = make_entry(client)
    bad_bodies = [
        [],                                  # legacy Block[] format
        [{"type": "text", "text": "old"}],   # legacy Block[] format
        "hello",
        42,
        {"type": "paragraph"},               # not a doc at the top level
        {"type": "doc", "content": "nope"},  # content must be a list
    ]
    for bad in bad_bodies:
        res = client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": bad})
        assert res.status_code == 400, f"accepted invalid body: {bad!r}"


def test_patch_rejects_oversized_body(client):
    entry_id = make_entry(client)
    big = {
        "type": "doc",
        "content": [{"type": "paragraph",
                     "content": [{"type": "text", "text": "x" * 1_100_000}]}],
    }
    res = client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": big})
    assert res.status_code == 400


# --- Auth -------------------------------------------------------------------

def test_me_reports_admin_in_dev_mode(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.get_json() == {"is_admin": True}


def test_me_reports_visitor_when_password_configured(auth_client):
    assert auth_client.get("/api/auth/me").get_json() == {"is_admin": False}


def test_login_with_correct_password(auth_client):
    res = log_in(auth_client)
    assert res.status_code == 200
    assert res.get_json() == {"is_admin": True}
    assert auth_client.get("/api/auth/me").get_json() == {"is_admin": True}


def test_login_with_wrong_password(auth_client):
    res = log_in(auth_client, "nope")
    assert res.status_code == 401
    assert auth_client.get("/api/auth/me").get_json() == {"is_admin": False}


def test_logout_clears_session(auth_client):
    log_in(auth_client)
    res = auth_client.post("/api/auth/logout")
    assert res.status_code == 200
    assert auth_client.get("/api/auth/me").get_json() == {"is_admin": False}
