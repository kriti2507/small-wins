import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point all file IO at a throwaway dir; module globals are read at call
    # time, so monkeypatching them is enough.
    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(app_module, "TOPICS_FILE", str(tmp_path / "topics.json"))
    monkeypatch.setattr(app_module, "UPLOADS_DIR", str(tmp_path / "uploads"))
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


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
