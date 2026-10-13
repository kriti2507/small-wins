"""One user can never see or change another user's data."""
import pytest

import app as app_module
from conftest import make_user

DOC = {"type": "doc", "content": [
    {"type": "paragraph", "content": [{"type": "text", "text": "mine"}]}]}
BUCKET_PREFIX = "https://proj.supabase.co/storage/v1/object/public/uploads/"


def slugs(c, headers=None):
    res = c.get("/api/topics", headers=headers or {})
    assert res.status_code == 200
    return [t["slug"] for t in res.get_json()]


def add_run(c, title="Run"):
    res = c.post("/api/topics/runs/entries", json={"date": "2026-10-01", "title": title})
    assert res.status_code == 201
    return res.get_json()["id"]


def test_each_user_lists_only_their_own_topics(client, second_client):
    assert client.post("/api/topics", json={"name": "Books"}).status_code == 201
    assert slugs(client) == ["runs", "books"]
    assert slugs(second_client) == ["runs"]


def test_two_users_can_have_the_same_topic(client, second_client):
    assert client.post("/api/topics", json={"name": "Books"}).status_code == 201
    assert second_client.post("/api/topics", json={"name": "Books"}).status_code == 201


def test_entry_ids_are_numbered_per_user(client, second_client):
    assert add_run(client) == 1
    assert add_run(client) == 2
    assert add_run(second_client) == 1


def test_another_users_topic_is_not_found(client, second_client):
    client.post("/api/topics", json={"name": "Books"})
    for method, path, body in [
        ("GET", "/api/topics/books/entries", None),
        ("POST", "/api/topics/books/entries", {"date": "2026-10-01"}),
        ("PATCH", "/api/topics/books", {"layout": "thumbnail"}),
        ("GET", "/api/topics/books/entries/1", None),
    ]:
        res = second_client.open(path, method=method, json=body)
        assert res.status_code == 404, f"{method} {path}"
        assert res.get_json()["error"] == "Unknown topic."

    books = next(t for t in client.get("/api/topics").get_json() if t["slug"] == "books")
    assert books["layout"] == "photo-top"
    assert client.get("/api/topics/books/entries").get_json() == []


def test_another_users_entry_is_not_found_and_stays_untouched(client, second_client):
    entry_id = add_run(client, "Mine")
    url = f"/api/topics/runs/entries/{entry_id}"
    assert client.patch(url, json={"body": DOC}).status_code == 200

    # second_client has its own "runs" topic, so these reach the entry lookup.
    assert second_client.get(url).status_code == 404
    assert second_client.patch(url, json={"title": "Hacked", "body": {"type": "doc"}}).status_code == 404
    assert second_client.delete(url).status_code == 404
    assert second_client.get("/api/topics/runs/entries").get_json() == []

    mine = client.get(url).get_json()
    assert mine["title"] == "Mine"
    assert mine["body"] == DOC


def test_deleting_an_entry_keeps_an_image_another_user_still_uses(client, second_client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")
    deleted = []
    monkeypatch.setattr(app_module.storage, "delete_object", lambda name: deleted.append(name))

    shared = BUCKET_PREFIX + "shared.jpg"
    mine = add_run(client)
    client.patch(f"/api/topics/runs/entries/{mine}", json={"image": shared})
    theirs = add_run(second_client)
    second_client.patch(f"/api/topics/runs/entries/{theirs}", json={"image": shared})

    assert client.delete(f"/api/topics/runs/entries/{mine}").status_code == 200
    assert "shared.jpg" not in deleted


def test_service_token_sees_only_the_acting_users_data(db_anon_client, monkeypatch):
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "svc-token")
    me = make_user("sub-me", "me@example.com")
    other = make_user("sub-other", "other@example.com")
    with app_module.app.app_context():
        app_module.db.add_topic(other, {"slug": "books", "name": "Books", "color": "red",
                                        "layout": "photo-top", "fields": []})

    def as_user(uid):
        return {"Authorization": "Bearer svc-token", "X-Acting-User": str(uid)}

    assert slugs(db_anon_client, as_user(me)) == ["runs"]
    assert slugs(db_anon_client, as_user(other)) == ["books"]
