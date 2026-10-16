"""One user can never see or change another user's data."""
import app as app_module
from conftest import make_user

DOC = {"type": "doc", "content": [
    {"type": "paragraph", "content": [{"type": "text", "text": "mine"}]}]}


def slugs(c):
    res = c.get("/api/topics")
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


def test_same_slug_and_entry_id_stay_separate(client, second_client):
    assert add_run(client, "Mine") == 1
    assert add_run(second_client, "Theirs") == 1
    url = "/api/topics/runs/entries/1"

    mine_body = DOC
    theirs_body = {"type": "doc", "content": []}
    assert client.patch(url, json={"body": mine_body}).status_code == 200
    assert second_client.patch(url, json={"body": theirs_body}).status_code == 200

    mine = client.get(url)
    assert mine.status_code == 200
    assert mine.get_json()["title"] == "Mine"
    assert mine.get_json()["body"] == mine_body

    theirs = second_client.get(url)
    assert theirs.status_code == 200
    assert theirs.get_json()["title"] == "Theirs"
    assert theirs.get_json()["body"] == theirs_body

    assert second_client.delete(url).status_code == 200

    mine_after = client.get(url)
    assert mine_after.status_code == 200
    assert mine_after.get_json()["title"] == "Mine"
    assert mine_after.get_json()["body"] == mine_body

    assert second_client.get(url).status_code == 404


def test_deleting_an_entry_never_touches_another_users_objects(client, second_client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")
    deleted = []
    monkeypatch.setattr(app_module.storage, "delete_object", lambda name: deleted.append(name))
    theirs_id = second_client.get("/api/auth/me").get_json()["user"]["id"]

    # Pasting someone else's image path into your own entry...
    theirs = f"/api/images/users/{theirs_id}/theirs.jpg"
    mine = add_run(client)
    assert client.patch(f"/api/topics/runs/entries/{mine}", json={"image": theirs}).status_code == 200
    # ...neither lets you read it...
    assert client.get(theirs).status_code == 404
    # ...nor delete it.
    assert client.delete(f"/api/topics/runs/entries/{mine}").status_code == 200
    assert deleted == []


def test_one_user_cannot_read_another_users_image(client, second_client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setattr(app_module.storage, "signed_read_url",
                        lambda name, expires_in: f"https://signed/{name}")
    mine_id = client.get("/api/auth/me").get_json()["user"]["id"]
    path = f"/api/images/users/{mine_id}/mine.jpg"
    assert client.get(path).status_code == 302
    assert second_client.get(path).status_code == 404
    assert second_client.get(path + "?size=thumb").status_code == 404
