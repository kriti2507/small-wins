import urllib.error
from io import BytesIO

import pytest

import app as app_module


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


def _set_storage_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_BUCKET", "uploads")


def my_id(client):
    return client.get("/api/auth/me").get_json()["user"]["id"]


def image_url(client, name):
    return f"/api/images/users/{my_id(client)}/{name}"


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


# --- image_urls_in -----------------------------------------------------------

def test_image_urls_in_handles_none_doc():
    assert app_module.image_urls_in(None) == set()


def test_image_urls_in_returns_empty_for_doc_without_figures():
    doc = {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "hi"}]},
    ]}
    assert app_module.image_urls_in(doc) == set()


def test_image_urls_in_finds_top_level_and_nested_figures():
    doc = {
        "type": "doc",
        "content": [
            {"type": "figure", "attrs": {"src": "https://x/top.jpg"}, "content": []},
            {"type": "blockquote", "content": [
                {"type": "figure", "attrs": {"src": "https://x/quoted.jpg"}, "content": []},
            ]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "hi"}]},
                    {"type": "figure", "attrs": {"src": "https://x/listed.jpg"}, "content": []},
                ]},
            ]},
        ],
    }
    assert app_module.image_urls_in(doc) == {
        "https://x/top.jpg", "https://x/quoted.jpg", "https://x/listed.jpg",
    }


def test_image_urls_in_ignores_missing_or_null_src():
    doc = {"type": "doc", "content": [
        {"type": "figure", "content": []},               # no attrs at all
        {"type": "figure", "attrs": {}, "content": []},   # attrs without src
        {"type": "figure", "attrs": {"src": None}, "content": []},
    ]}
    assert app_module.image_urls_in(doc) == set()


def test_image_urls_in_tolerates_missing_or_malformed_content():
    doc = {"type": "doc", "content": [
        {"type": "paragraph"},  # no "content" key at all
        {"type": "figure", "attrs": {"src": "https://x/ok.jpg"}, "content": "not-a-list"},
    ]}
    assert app_module.image_urls_in(doc) == {"https://x/ok.jpg"}


# --- Delete entry -------------------------------------------------------------

def test_delete_entry_removes_it(client):
    entry_id = make_entry(client)
    res = client.delete(f"/api/topics/runs/entries/{entry_id}")
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}
    assert client.get(f"/api/topics/runs/entries/{entry_id}").status_code == 404


def test_delete_entry_cascades_the_post_body(client):
    import db
    with client.session_transaction() as s:
        uid = s["user_id"]
    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": DOC})
    assert db.load_post(uid, "runs", entry_id) == DOC

    res = client.delete(f"/api/topics/runs/entries/{entry_id}")
    assert res.status_code == 200

    # Querying the posts table directly (rather than just re-GETting the
    # entry) proves the FK cascade actually ran the delete, not merely that
    # the entries row is gone.
    assert db.load_post(uid, "runs", entry_id) is None


def test_delete_entry_unknown_topic_404(client):
    res = client.delete("/api/topics/nope/entries/1")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Unknown topic."


def test_delete_entry_unknown_entry_404(client):
    res = client.delete("/api/topics/runs/entries/999")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Unknown entry."


def test_delete_entry_deletes_hero_and_body_images_and_their_thumbnails(client, monkeypatch):
    _set_storage_env(monkeypatch)
    deleted = []
    monkeypatch.setattr(app_module.storage, "delete_object", lambda name: deleted.append(name))
    uid = my_id(client)

    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"image": image_url(client, "hero.jpg")})
    doc = {"type": "doc", "content": [
        {"type": "figure", "attrs": {"src": image_url(client, "body.jpg")}, "content": []},
    ]}
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": doc})

    res = client.delete(f"/api/topics/runs/entries/{entry_id}")
    assert res.status_code == 200
    assert set(deleted) == {
        f"users/{uid}/hero.jpg", f"users/{uid}/hero.thumb",
        f"users/{uid}/body.jpg", f"users/{uid}/body.thumb",
    }


def test_delete_entry_tolerates_a_missing_thumbnail(client, monkeypatch):
    _set_storage_env(monkeypatch)
    deleted = []

    def delete(name):
        if name.endswith(".thumb"):
            raise app_module.storage.NotFound(name)
        deleted.append(name)
    monkeypatch.setattr(app_module.storage, "delete_object", delete)
    warnings = []
    monkeypatch.setattr(app_module.app.logger, "warning", lambda *a: warnings.append(a))

    entry_id = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"image": image_url(client, "a.gif")})

    assert client.delete(f"/api/topics/runs/entries/{entry_id}").status_code == 200
    assert deleted == [f"users/{my_id(client)}/a.gif"]
    assert warnings == []  # a GIF has no thumbnail; that's not a failure


def test_delete_entry_keeps_image_still_referenced_by_another_entry(client, monkeypatch):
    _set_storage_env(monkeypatch)
    deleted = []
    monkeypatch.setattr(app_module.storage, "delete_object", lambda name: deleted.append(name))

    shared_url = image_url(client, "shared.jpg")
    entry1 = make_entry(client)
    entry2 = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry1}", json={"image": shared_url})
    client.patch(f"/api/topics/runs/entries/{entry2}", json={"image": shared_url})

    res = client.delete(f"/api/topics/runs/entries/{entry1}")
    assert res.status_code == 200
    assert deleted == []

    # the surviving entry can still be fetched with its image intact
    assert client.get(f"/api/topics/runs/entries/{entry2}").get_json()["image"] == shared_url


def test_delete_entry_keeps_figure_copied_into_another_post(client, monkeypatch):
    # TipTap lets you copy a figure node between posts, duplicating its src.
    # A hero-image share alone (as in the test above) only exercises
    # db.all_entry_images(); this pins the in-body half of
    # referenced_image_urls(), across two different topics to also cover
    # the cross-topic union.
    _set_storage_env(monkeypatch)
    deleted = []
    monkeypatch.setattr(app_module.storage, "delete_object", lambda name: deleted.append(name))

    res = client.post("/api/topics", json={"name": "Books"})
    assert res.status_code == 201

    shared_url = image_url(client, "copied.jpg")
    doc = {"type": "doc", "content": [
        {"type": "figure", "attrs": {"src": shared_url}, "content": []},
    ]}
    entry1 = make_entry(client)
    client.patch(f"/api/topics/runs/entries/{entry1}", json={"body": doc})
    entry2_res = client.post("/api/topics/books/entries", json={"date": "2026-07-09"})
    assert entry2_res.status_code == 201
    entry2 = entry2_res.get_json()["id"]
    client.patch(f"/api/topics/books/entries/{entry2}", json={"body": doc})

    res = client.delete(f"/api/topics/runs/entries/{entry1}")
    assert res.status_code == 200
    assert deleted == []

    # the surviving post in the other topic still resolves the shared figure
    survivor = client.get(f"/api/topics/books/entries/{entry2}").get_json()
    assert survivor["body"] == doc


def test_delete_entry_skips_externally_hosted_image(client, monkeypatch):
    _set_storage_env(monkeypatch)
    deleted = []
    monkeypatch.setattr(app_module.storage, "delete_object", lambda name: deleted.append(name))

    entry_id = make_entry(client)
    external_url = "https://example.com/random/photo.jpg"
    doc = {"type": "doc", "content": [
        {"type": "figure", "attrs": {"src": external_url}, "content": []},
    ]}
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"body": doc})

    res = client.delete(f"/api/topics/runs/entries/{entry_id}")
    assert res.status_code == 200
    assert deleted == []


def test_delete_entry_leaves_old_public_urls_alone(client, monkeypatch):
    _set_storage_env(monkeypatch)
    deleted = []
    monkeypatch.setattr(app_module.storage, "delete_object", lambda name: deleted.append(name))

    entry_id = make_entry(client)
    old = "https://proj.supabase.co/storage/v1/object/public/uploads/old.jpg"
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"image": old})

    assert client.delete(f"/api/topics/runs/entries/{entry_id}").status_code == 200
    assert deleted == []


def test_delete_entry_storage_failure_still_returns_200(client, monkeypatch):
    _set_storage_env(monkeypatch)

    def boom(name):
        raise RuntimeError("storage down")

    monkeypatch.setattr(app_module.storage, "delete_object", boom)

    entry_id = make_entry(client)
    hero_url = image_url(client, "hero.jpg")
    client.patch(f"/api/topics/runs/entries/{entry_id}", json={"image": hero_url})

    res = client.delete(f"/api/topics/runs/entries/{entry_id}")
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}


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

def sign_ok(monkeypatch, seen=None):
    """Stub the Supabase signing call, recording the key it was asked to sign."""
    _set_storage_env(monkeypatch)

    def fake(name, expires_in=None):
        if seen is not None:
            seen.append(name)
        return f"https://proj.supabase.co/storage/v1/object/upload/sign/uploads/{name}?token=t"
    monkeypatch.setattr(app_module.storage, "signed_upload_url", fake)


def test_sign_upload_mints_a_key_under_the_users_prefix(no_db_client, monkeypatch):
    keys = []
    sign_ok(monkeypatch, keys)

    res = no_db_client.post("/api/uploads/sign", json={"ext": "png"})

    assert res.status_code == 201
    body = res.get_json()
    assert len(keys) == 1
    assert keys[0].startswith("users/1/") and keys[0].endswith(".png")
    assert body["upload_url"].endswith(f"/{keys[0]}?token=t")
    # The DB stores the app path, never a Supabase URL.
    assert body["url"] == f"/api/images/{keys[0]}"
    assert "thumb_upload_url" not in body


def test_sign_upload_adds_a_thumbnail_url_when_asked(no_db_client, monkeypatch):
    keys = []
    sign_ok(monkeypatch, keys)

    res = no_db_client.post("/api/uploads/sign", json={"ext": "jpg", "thumb": True})

    assert res.status_code == 201
    body = res.get_json()
    full, thumb = keys
    assert thumb == full[: -len(".jpg")] + ".thumb"
    assert body["thumb_upload_url"].endswith(f"/{thumb}?token=t")
    assert body["url"] == f"/api/images/{full}"


@pytest.mark.parametrize("thumb", ["true", 1])
def test_sign_upload_requires_the_literal_true_for_thumb(no_db_client, monkeypatch, thumb):
    keys = []
    sign_ok(monkeypatch, keys)

    res = no_db_client.post("/api/uploads/sign", json={"ext": "png", "thumb": thumb})

    assert res.status_code == 201
    assert "thumb_upload_url" not in res.get_json()


def test_sign_upload_reports_thumbnail_signing_failure_as_json_502(no_db_client, monkeypatch):
    _set_storage_env(monkeypatch)

    def fake(name, expires_in=None):
        if name.endswith(".thumb"):
            raise urllib.error.HTTPError("u", 500, "err", {}, BytesIO(b"down"))
        return f"https://proj.supabase.co/storage/v1/object/upload/sign/uploads/{name}?token=t"
    monkeypatch.setattr(app_module.storage, "signed_upload_url", fake)

    res = no_db_client.post("/api/uploads/sign", json={"ext": "jpg", "thumb": True})

    assert res.status_code == 502
    assert res.get_json()["error"]


def test_sign_upload_ignores_a_client_supplied_key(no_db_client, monkeypatch):
    keys = []
    sign_ok(monkeypatch, keys)

    res = no_db_client.post("/api/uploads/sign",
                            json={"ext": "png", "name": "../../etc/passwd"})

    assert res.status_code == 201
    assert ".." not in keys[0]
    # Whatever we mint must be readable and deletable by its owner.
    assert app_module.storage.user_key(keys[0], 1) == keys[0]


# --- Reading images -----------------------------------------------------------

def read_ok(monkeypatch, seen, missing=()):
    """Stub Supabase's read signing; keys in `missing` don't exist."""
    _set_storage_env(monkeypatch)

    def fake(name, expires_in):
        seen.append((name, expires_in))
        if name in missing:
            raise app_module.storage.NotFound(name)
        return f"https://proj.supabase.co/storage/v1/object/sign/uploads/{name}?token=t"
    monkeypatch.setattr(app_module.storage, "signed_read_url", fake)


def test_read_image_redirects_to_a_signed_url(no_db_client, monkeypatch):
    seen = []
    read_ok(monkeypatch, seen)

    res = no_db_client.get("/api/images/users/1/abc.jpg")

    assert res.status_code == 302
    assert res.headers["Location"] == (
        "https://proj.supabase.co/storage/v1/object/sign/uploads/users/1/abc.jpg?token=t")
    # Shorter than the signature's hour, so a cached redirect is never stale.
    assert res.headers["Cache-Control"] == "private, max-age=3000"
    assert seen == [("users/1/abc.jpg", 3600)]


def test_read_image_thumb_signs_the_thumbnail(no_db_client, monkeypatch):
    seen = []
    read_ok(monkeypatch, seen)

    res = no_db_client.get("/api/images/users/1/abc.jpg?size=thumb")

    assert res.status_code == 302
    assert res.headers["Location"].endswith("/users/1/abc.thumb?token=t")
    assert seen == [("users/1/abc.thumb", 3600)]


def test_read_image_thumb_falls_back_to_the_full_image(no_db_client, monkeypatch):
    seen = []
    read_ok(monkeypatch, seen, missing={"users/1/abc.thumb"})

    res = no_db_client.get("/api/images/users/1/abc.gif?size=thumb")

    assert res.status_code == 302
    assert res.headers["Location"].endswith("/users/1/abc.gif?token=t")
    assert seen == [("users/1/abc.thumb", 3600), ("users/1/abc.gif", 3600)]


def test_read_image_thumb_404s_when_both_are_missing(no_db_client, monkeypatch):
    seen = []
    read_ok(monkeypatch, seen, missing={"users/1/abc.thumb", "users/1/abc.gif"})

    res = no_db_client.get("/api/images/users/1/abc.gif?size=thumb")

    assert res.status_code == 404


def test_read_image_thumb_signing_failure_skips_the_full_image(no_db_client, monkeypatch):
    _set_storage_env(monkeypatch)
    seen = []

    def fake(name, expires_in):
        seen.append(name)
        if name.endswith(".thumb"):
            raise urllib.error.HTTPError("u", 500, "err", {}, BytesIO(b"down"))
        return f"https://proj.supabase.co/storage/v1/object/sign/uploads/{name}?token=t"
    monkeypatch.setattr(app_module.storage, "signed_read_url", fake)

    res = no_db_client.get("/api/images/users/1/abc.jpg?size=thumb")

    assert res.status_code == 502
    # A non-NotFound failure must not be papered over by the fallback.
    assert seen == ["users/1/abc.thumb"]


@pytest.mark.parametrize("path", [
    "/api/images/users/2/abc.jpg",          # someone else's
    "/api/images/abc.jpg",                  # outside users/
    "/api/images/users/1/a/b.jpg",
    "/api/images/users/1/..%2F2%2Fabc.jpg",
    "/api/images/users/1/%2e%2e",
    "/api/images/users/12/abc.jpg",
])
def test_read_image_404s_for_keys_that_are_not_yours(no_db_client, monkeypatch, path):
    seen = []
    read_ok(monkeypatch, seen)
    res = no_db_client.get(path)
    assert res.status_code == 404
    assert seen == []  # never asked Supabase, so nothing can be probed


def test_read_image_404s_when_the_object_is_gone(no_db_client, monkeypatch):
    seen = []
    read_ok(monkeypatch, seen, missing={"users/1/abc.jpg"})
    assert no_db_client.get("/api/images/users/1/abc.jpg").status_code == 404


def test_read_image_reports_storage_failure_as_json_502(no_db_client, monkeypatch):
    _set_storage_env(monkeypatch)

    def boom(name, expires_in):
        raise urllib.error.HTTPError("u", 500, "err", {}, BytesIO(b"down"))
    monkeypatch.setattr(app_module.storage, "signed_read_url", boom)

    res = no_db_client.get("/api/images/users/1/abc.jpg")
    assert res.status_code == 502
    assert res.get_json()["error"]


def test_read_image_needs_sign_in(anon_client):
    assert anon_client.get("/api/images/users/1/abc.jpg").status_code == 401


@pytest.mark.parametrize("ext", ["heic", "svg", "exe", "", "png.exe", "PNG/../x"])
def test_sign_upload_rejects_unsupported_extensions(no_db_client, monkeypatch, ext):
    sign_ok(monkeypatch)
    res = no_db_client.post("/api/uploads/sign", json={"ext": ext})
    assert res.status_code == 400
    assert res.get_json()["error"] == "Unsupported file type."


def test_sign_upload_normalises_extension_case_and_leading_dot(no_db_client, monkeypatch):
    keys = []
    sign_ok(monkeypatch, keys)
    res = no_db_client.post("/api/uploads/sign", json={"ext": ".JPG"})
    assert res.status_code == 201
    assert keys[0].endswith(".jpg")


def test_sign_upload_rejects_malformed_payloads_as_json(no_db_client, monkeypatch):
    sign_ok(monkeypatch)
    bad = [("[1, 2]", "application/json"), ("null", "application/json"),
           ("not json", "text/plain"), ("", "application/json")]
    for body, ctype in bad:
        res = no_db_client.post("/api/uploads/sign", data=body, content_type=ctype)
        assert res.status_code == 400, f"{body!r} -> {res.status_code}"
        assert res.headers["Content-Type"].startswith("application/json")


def test_sign_upload_reports_storage_failure_as_json_not_html(no_db_client, monkeypatch):
    def boom(name, expires_in=None):
        raise urllib.error.HTTPError("u", 400, "Bad Request", {}, BytesIO(b"nope"))
    monkeypatch.setattr(app_module.storage, "signed_upload_url", boom)

    res = no_db_client.post("/api/uploads/sign", json={"ext": "png"})

    # A 500 HTML page here is unparseable by the client; it must stay JSON.
    assert res.status_code == 502
    assert res.headers["Content-Type"].startswith("application/json")
    assert res.get_json()["error"]


# --- Access control -----------------------------------------------------------

# Auth endpoints decide for themselves; every other route must need sign-in.
PUBLIC_ENDPOINTS = {"auth.me", "auth.google_login", "auth.google_callback", "auth.logout"}


def protected_routes():
    for rule in app_module.app.url_map.iter_rules():
        if rule.endpoint in PUBLIC_ENDPOINTS:
            continue
        path = (rule.rule.replace("<int:entry_id>", "1").replace("<slug>", "runs")
                .replace("<path:key>", "users/1/a.jpg"))
        assert "<" not in path, f"teach protected_routes about {rule.rule}"
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            yield method, path


def test_every_route_needs_sign_in(anon_client):
    routes = list(protected_routes())
    assert len(routes) >= 9  # guards against the url_map walk silently finding nothing
    for method, path in routes:
        res = anon_client.open(path, method=method, json={})
        assert res.status_code == 401, f"{method} {path} -> {res.status_code}"
        assert res.get_json()["error"] == "Sign in to continue."


def test_reads_and_writes_work_when_signed_in(client):
    assert client.get("/api/topics").status_code == 200
    res = client.post("/api/topics/runs/entries", json={"date": "2026-07-10", "title": "Run"})
    assert res.status_code == 201


def test_me_returns_the_signed_in_user(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    user = res.get_json()["user"]
    assert (user["email"], user["name"], user["avatar_url"]) == ("test@example.com", "Test", None)
    assert isinstance(user["id"], int)


def test_me_is_401_when_signed_out(db_anon_client):
    res = db_anon_client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.get_json()["error"] == "Not signed in."


def test_me_drops_a_session_whose_user_is_gone(db_anon_client):
    with db_anon_client.session_transaction() as s:
        s["user_id"] = 999999
    assert db_anon_client.get("/api/auth/me").status_code == 401
    with db_anon_client.session_transaction() as s:
        assert "user_id" not in s


def test_logout_signs_out(client):
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/topics").status_code == 401


# --- MCP service token --------------------------------------------------------

from conftest import make_user  # noqa: E402

SVC = {"Authorization": "Bearer svc-token"}


def sign_bad_ext(c, headers=None):
    # sign_upload rejects .exe with 400 only after login_required passes, so
    # the status says which side of the check we landed on.
    return c.post("/api/uploads/sign", json={"ext": "exe"}, headers=headers or {})


def test_signed_in_session_passes_the_guard(no_db_client):
    assert sign_bad_ext(no_db_client).status_code == 400


def test_service_token_with_a_known_acting_user_passes(db_anon_client, monkeypatch):
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "svc-token")
    uid = make_user("sub-me", "me@example.com")
    res = sign_bad_ext(db_anon_client, {**SVC, "X-Acting-User": str(uid)})
    assert res.status_code == 400


@pytest.mark.parametrize("acting", [
    None, "", "abc", "-1", "0", "1.5", " 1", "99999999", "1" * 30, "١",
])
def test_service_token_without_a_known_acting_user_is_refused(db_anon_client, monkeypatch, acting):
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "svc-token")
    headers = dict(SVC)
    if acting is not None:
        headers["X-Acting-User"] = acting
    res = sign_bad_ext(db_anon_client, headers)
    assert res.status_code == 401
    assert res.get_json()["error"] == "Sign in to continue."


def test_acting_user_header_is_ignored_without_the_service_token(db_anon_client, monkeypatch):
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "svc-token")
    uid = make_user("sub-me", "me@example.com")
    for auth_header in ({}, {"Authorization": "Bearer nope"}):
        res = sign_bad_ext(db_anon_client, {**auth_header, "X-Acting-User": str(uid)})
        assert res.status_code == 401, auth_header


def test_wrong_or_malformed_service_token_is_refused(anon_client, monkeypatch):
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "svc-token")
    for headers in (
        {},
        {"Authorization": "Bearer nope"},
        {"Authorization": "svc-token"},
        {"Authorization": "Basic svc-token"},
    ):
        assert sign_bad_ext(anon_client, {**headers, "X-Acting-User": "1"}).status_code == 401, headers


def test_service_token_ignored_when_unset(anon_client):
    for token in ("", "None"):
        headers = {"Authorization": f"Bearer {token}", "X-Acting-User": "1"}
        assert sign_bad_ext(anon_client, headers).status_code == 401


def test_login_required_exposes_the_acting_user_on_g(no_db_client, monkeypatch):
    seen = []

    def spy(name, expires_in=None):
        seen.append(app_module.g.user_id)
        raise RuntimeError("stop here")  # the route turns this into a 502
    monkeypatch.setattr(app_module.storage, "signed_upload_url", spy)
    no_db_client.post("/api/uploads/sign", json={"ext": "png"})
    assert seen == [1]  # no_db_client's session user_id
