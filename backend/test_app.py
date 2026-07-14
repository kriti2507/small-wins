from io import BytesIO

import pytest
from werkzeug.security import generate_password_hash

import app as app_module

TEST_PASSWORD = "correct horse"
TEST_HASH = generate_password_hash(TEST_PASSWORD, method="pbkdf2:sha256")


@pytest.fixture()
def client(test_db, monkeypatch):
    # test_db (conftest) points db.py at the test database and truncates tables.
    monkeypatch.setattr(app_module, "ADMIN_PASSWORD_HASH", None, raising=False)
    monkeypatch.setattr(app_module, "LOGIN_ATTEMPTS", {}, raising=False)
    app_module.app.config["TESTING"] = True
    app_module.app.config["SESSION_COOKIE_SECURE"] = False
    return app_module.app.test_client()


@pytest.fixture()
def auth_client(client, monkeypatch):
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
    res = client.post("/api/topics/runs/entries", json={"date": "2026-07-09", "title": "Run"})
    assert res.status_code == 201
    return res.get_json()["id"]


# --- Entry body / fields ----------------------------------------------------

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
        [], [{"type": "text", "text": "old"}], "hello", 42,
        {"type": "paragraph"}, {"type": "doc", "content": "nope"},
    ]
    for bad in bad_bodies:
        res = client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": bad})
        assert res.status_code == 400, f"accepted invalid body: {bad!r}"


def test_patch_rejects_oversized_body(client):
    entry_id = make_entry(client)
    big = {"type": "doc", "content": [{"type": "paragraph",
           "content": [{"type": "text", "text": "x" * 1_100_000}]}]}
    res = client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": big})
    assert res.status_code == 400


def test_patch_updates_text_and_number_fields(client):
    entry_id = make_entry(client)
    res = client.patch(
        f"/api/topics/runs/entries/{entry_id}",
        json={"title": "Morning run", "distance": "5.25"},
    )
    assert res.status_code == 200
    entry = client.get(f"/api/topics/runs/entries/{entry_id}").get_json()
    assert entry["title"] == "Morning run"
    assert entry["distance"] == 5.25


def test_patch_updates_date_and_image(client):
    entry_id = make_entry(client)
    client.patch(
        f"/api/topics/runs/entries/{entry_id}",
        json={"date": "2026-07-13", "image": "https://cdn/x.jpg"},
    )
    entry = client.get(f"/api/topics/runs/entries/{entry_id}").get_json()
    assert entry["date"] == "2026-07-13"
    assert entry["image"] == "https://cdn/x.jpg"


def test_patch_coerces_pace_and_blanks_to_none(client):
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"pace": 315})
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"distance": ""})
    entry = client.get(f"/api/topics/runs/entries/{entry_id}").get_json()
    assert entry["pace"] == 315.0
    assert entry["distance"] is None


def test_patch_ignores_unknown_keys(client):
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"bogus": "x", "id": 999})
    entry = client.get(f"/api/topics/runs/entries/{entry_id}").get_json()
    assert "bogus" not in entry
    assert entry["id"] == entry_id


def test_patch_updates_fields_and_body_together(client):
    entry_id = make_entry(client)
    res = client.patch(
        f"/api/topics/runs/entries/{entry_id}",
        json={"title": "Combined", "body": DOC},
    )
    assert res.status_code == 200
    entry = client.get(f"/api/topics/runs/entries/{entry_id}").get_json()
    assert entry["title"] == "Combined"
    assert entry["body"] == DOC


def test_api_responses_hide_the_post_reference(client):
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    single = client.get(f"/api/topics/runs/entries/{entry_id}").get_json()
    assert single["body"] == DOC
    assert "post" not in single
    listed = client.get("/api/topics/runs/entries").get_json()
    entry = next(e for e in listed if e["id"] == entry_id)
    assert entry["body"] == DOC
    assert "post" not in entry


def test_repeated_saves_keep_latest_body(client):
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    doc2 = {"type": "doc", "content": [{"type": "paragraph",
            "content": [{"type": "text", "text": "edited"}]}]}
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": doc2})
    assert client.get(f"/api/topics/runs/entries/{entry_id}").get_json()["body"] == doc2


def test_entry_without_post_has_no_body(client):
    entry_id = make_entry(client)
    single = client.get(f"/api/topics/runs/entries/{entry_id}")
    assert single.status_code == 200
    assert "body" not in single.get_json()


def test_unknown_topic_and_entry_404(client):
    assert client.get("/api/topics/nope/entries").status_code == 404
    assert client.get("/api/topics/runs/entries/999").status_code == 404


# --- Topics -----------------------------------------------------------------

def test_add_topic_appends_and_is_listed(client):
    res = client.post("/api/topics", json={
        "name": "Books", "color": "red", "layout": "photo-top",
        "fields": [{"label": "Author", "type": "text", "direction": "none"}],
    })
    assert res.status_code == 201
    slugs = [t["slug"] for t in client.get("/api/topics").get_json()]
    assert slugs == ["runs", "books"]


def test_add_duplicate_topic_conflicts(client):
    client.post("/api/topics", json={"name": "Books"})
    res = client.post("/api/topics", json={"name": "Books"})
    assert res.status_code == 409


def test_set_topic_layout(client):
    res = client.patch("/api/topics/runs", json={"layout": "thumbnail"})
    assert res.status_code == 200
    assert res.get_json()["layout"] == "thumbnail"


# --- Uploads ----------------------------------------------------------------

def test_upload_returns_storage_url(client, monkeypatch):
    monkeypatch.setattr(app_module.storage, "upload_bytes",
                        lambda name, data, ctype: f"https://cdn/{name}")
    res = client.post(
        "/api/uploads",
        data={"file": (BytesIO(b"x"), "photo.png")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 201
    assert res.get_json()["url"].startswith("https://cdn/")


# --- Auth -------------------------------------------------------------------

def test_me_reports_admin_in_dev_mode(client):
    assert client.get("/api/auth/me").get_json() == {"is_admin": True}


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
    assert auth_client.post("/api/auth/logout").status_code == 200
    assert auth_client.get("/api/auth/me").get_json() == {"is_admin": False}


def test_login_rejects_malformed_payloads(auth_client):
    bad = [
        ("[1, 2]", "application/json"),
        ('{"password": 123}', "application/json"),
        ("not json", "text/plain"),
    ]
    for body, ctype in bad:
        res = auth_client.post("/api/auth/login", data=body, content_type=ctype)
        assert res.status_code == 401, f"{body!r} -> {res.status_code}"


def test_writes_locked_out_for_visitors(auth_client):
    checks = [
        ("post", "/api/topics", {"json": {"name": "Reads"}}),
        ("patch", "/api/topics/runs", {"json": {"layout": "thumbnail"}}),
        ("post", "/api/topics/runs/entries", {"json": {"date": "2026-07-10"}}),
        ("patch", "/api/topics/runs/entries/1",
         {"json": {"body": {"type": "doc", "content": []}}}),
        ("post", "/api/uploads", {"data": {}}),
    ]
    for method, url, kwargs in checks:
        res = getattr(auth_client, method)(url, **kwargs)
        assert res.status_code == 403, f"{method} {url} -> {res.status_code}"
        assert res.get_json()["error"] == "Only admin can make changes."


def test_writes_allowed_after_login(auth_client):
    log_in(auth_client)
    res = auth_client.post("/api/topics/runs/entries",
                           json={"date": "2026-07-10", "title": "Run"})
    assert res.status_code == 201


def test_writes_locked_again_after_logout(auth_client):
    log_in(auth_client)
    auth_client.post("/api/auth/logout")
    res = auth_client.post("/api/topics/runs/entries", json={"date": "2026-07-10"})
    assert res.status_code == 403


def test_reads_stay_public(auth_client):
    assert auth_client.get("/api/topics").status_code == 200
    assert auth_client.get("/api/topics/runs/entries").status_code == 200


def test_login_rate_limited_after_five_failures(auth_client):
    for _ in range(5):
        assert log_in(auth_client, "wrong").status_code == 401
    assert log_in(auth_client, "wrong").status_code == 429
    assert log_in(auth_client).status_code == 429
