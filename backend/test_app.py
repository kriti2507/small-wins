import json
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


def test_login_rejects_malformed_payloads(auth_client):
    bad = [
        ("[1, 2]", "application/json"),          # JSON but not an object
        ('{"password": 123}', "application/json"),  # non-string password
        ("not json", "text/plain"),               # not JSON at all
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
    res = auth_client.post(
        "/api/topics/runs/entries", json={"date": "2026-07-10", "title": "Run"}
    )
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
    res = log_in(auth_client, "wrong")
    assert res.status_code == 429
    # Even the correct password is refused while rate-limited.
    assert log_in(auth_client).status_code == 429


# --- Post file storage --------------------------------------------------------

def test_post_ref_names_file_by_id_and_title():
    ref = app_module.post_ref({"id": 3, "title": "Morning Tempo!"}, "runs")
    assert ref == "posts/runs/3_morning_tempo.json"


def test_post_ref_without_usable_title_uses_id_only():
    assert app_module.post_ref({"id": 7, "title": "  "}, "runs") == "posts/runs/7.json"
    assert app_module.post_ref({"id": 8}, "runs") == "posts/runs/8.json"


def test_resolve_post_path_stays_inside_posts_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    ok = app_module.resolve_post_path("posts/runs/1_run.json")
    assert ok == str(tmp_path / "posts" / "runs" / "1_run.json")
    assert app_module.resolve_post_path("../evil.json") is None
    assert app_module.resolve_post_path("posts/../topics.json") is None
    assert app_module.resolve_post_path("topics.json") is None
    assert app_module.resolve_post_path("/etc/passwd") is None
    assert app_module.resolve_post_path("") is None
    assert app_module.resolve_post_path("posts") is None
    assert app_module.resolve_post_path("postsx/a.json") is None
    assert app_module.resolve_post_path(None) is None
    assert app_module.resolve_post_path(5) is None


def test_patch_stores_body_in_post_file(client, tmp_path):
    entry_id = make_entry(client)
    res = client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    assert res.status_code == 200
    patched = res.get_json()
    assert patched["body"] == DOC
    assert "post" not in patched

    post_file = tmp_path / "posts" / "runs" / f"{entry_id}_run.json"
    assert json.loads(post_file.read_text()) == DOC

    stored = json.loads((tmp_path / "runs.json").read_text())
    stored_entry = next(e for e in stored if e["id"] == entry_id)
    assert "body" not in stored_entry
    assert stored_entry["post"] == f"posts/runs/{entry_id}_run.json"


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


def test_repeated_saves_reuse_the_same_post_file(client, tmp_path):
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    doc2 = {"type": "doc", "content": [{"type": "paragraph",
            "content": [{"type": "text", "text": "edited"}]}]}
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": doc2})

    posts = list((tmp_path / "posts" / "runs").iterdir())
    assert len(posts) == 1
    assert json.loads(posts[0].read_text()) == doc2


def test_patch_drops_stale_inline_body_from_storage(client, tmp_path):
    entry_id = make_entry(client)
    # Simulate an un-migrated entry: inline body, no post reference.
    stored = json.loads((tmp_path / "runs.json").read_text())
    next(e for e in stored if e["id"] == entry_id)["body"] = DOC
    (tmp_path / "runs.json").write_text(json.dumps(stored))

    res = client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    assert res.status_code == 200

    stored = json.loads((tmp_path / "runs.json").read_text())
    stored_entry = next(e for e in stored if e["id"] == entry_id)
    assert "body" not in stored_entry
    assert stored_entry["post"] == f"posts/runs/{entry_id}_run.json"


def test_missing_post_file_degrades_to_no_body(client, tmp_path):
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    (tmp_path / "posts" / "runs" / f"{entry_id}_run.json").unlink()

    single = client.get(f"/api/topics/runs/entries/{entry_id}")
    assert single.status_code == 200
    assert "body" not in single.get_json()
    assert client.get("/api/topics/runs/entries").status_code == 200


def test_corrupt_post_file_degrades_to_no_body(client, tmp_path):
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    (tmp_path / "posts" / "runs" / f"{entry_id}_run.json").write_text("not json{{")

    res = client.get(f"/api/topics/runs/entries/{entry_id}")
    assert res.status_code == 200
    assert "body" not in res.get_json()


def test_escaping_reference_is_ignored(client, tmp_path):
    entry_id = make_entry(client)
    stored = json.loads((tmp_path / "runs.json").read_text())
    next(e for e in stored if e["id"] == entry_id)["post"] = "../topics.json"
    (tmp_path / "runs.json").write_text(json.dumps(stored))

    res = client.get(f"/api/topics/runs/entries/{entry_id}")
    assert res.status_code == 200
    body = res.get_json()
    assert "body" not in body and "post" not in body


def seed_legacy_entries(client, tmp_path, entries):
    client.get("/api/topics")  # seeds the default "runs" topic
    (tmp_path / "runs.json").write_text(json.dumps(entries))


def test_migrates_inline_doc_bodies_on_read(client, tmp_path):
    legacy = [
        {"id": 1, "date": "2026-07-01", "title": "Old Run", "body": DOC},
        {"id": 2, "date": "2026-07-02", "title": "No Post"},
    ]
    seed_legacy_entries(client, tmp_path, legacy)

    res = client.get("/api/topics/runs/entries")
    assert res.status_code == 200
    assert res.get_json()[0]["body"] == DOC

    post_file = tmp_path / "posts" / "runs" / "1_old_run.json"
    assert json.loads(post_file.read_text()) == DOC

    stored = json.loads((tmp_path / "runs.json").read_text())
    assert "body" not in stored[0]
    assert stored[0]["post"] == "posts/runs/1_old_run.json"
    assert "post" not in stored[1]

    assert json.loads((tmp_path / "runs.json.bak").read_text()) == legacy


def test_migrates_legacy_block_bodies(client, tmp_path):
    blocks = [
        {"type": "text", "text": "line one\n\nline two"},
        {"type": "image", "url": "/api/uploads/x.jpg"},
    ]
    seed_legacy_entries(
        client, tmp_path,
        [{"id": 1, "date": "2026-07-01", "title": "Blocks", "body": blocks}],
    )

    body = client.get("/api/topics/runs/entries/1").get_json()["body"]
    assert body == {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "line one"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "line two"}]},
            {"type": "figure", "attrs": {"src": "/api/uploads/x.jpg", "width": "normal"}},
        ],
    }


def test_migration_is_idempotent(client, tmp_path):
    legacy = [{"id": 1, "date": "2026-07-01", "title": "Old Run", "body": DOC}]
    seed_legacy_entries(client, tmp_path, legacy)

    client.get("/api/topics/runs/entries")
    migrated = (tmp_path / "runs.json").read_text()

    client.get("/api/topics/runs/entries")
    assert (tmp_path / "runs.json").read_text() == migrated
    # the backup still holds the original, not a re-copy of migrated data
    assert json.loads((tmp_path / "runs.json.bak").read_text()) == legacy


def test_non_doc_post_file_degrades_to_no_body(client, tmp_path):
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    (tmp_path / "posts" / "runs" / f"{entry_id}_run.json").write_text('{"a": 1}')

    res = client.get(f"/api/topics/runs/entries/{entry_id}")
    assert res.status_code == 200
    assert "body" not in res.get_json()
