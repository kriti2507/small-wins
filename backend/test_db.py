import pytest


@pytest.fixture()
def uid(app_ctx):
    import db
    return db.upsert_user("sub-a", "a@example.com", "A", None)["id"]


@pytest.fixture()
def other(app_ctx):
    import db
    return db.upsert_user("sub-b", "b@example.com", "B", None)["id"]


BOOKS = {"slug": "books", "name": "Books", "color": "red", "layout": "photo-top",
         "fields": [{"key": "author", "label": "Author", "type": "text", "direction": "none"}]}


def test_get_conn_can_query_the_schema(app_ctx):
    import db
    conn = db.get_conn()
    rows = conn.execute(
        "select table_name from information_schema.tables "
        "where table_schema='public' order by table_name"
    ).fetchall()
    names = {r["table_name"] for r in rows}
    assert {"topics", "entries", "posts", "users"} <= names


def test_seeds_default_topics_when_the_user_has_none(uid):
    import db
    topics = db.load_topics(uid)
    assert [t["slug"] for t in topics] == ["workout", "journal"]
    assert topics[0]["fields"][0]["key"] == "title"


def test_seeding_is_per_user(uid, other):
    import db
    db.add_topic(uid, BOOKS)  # uid now has topics, so no seed for uid
    assert [t["slug"] for t in db.load_topics(uid)] == ["books"]
    assert [t["slug"] for t in db.load_topics(other)] == ["workout", "journal"]


def test_add_topic_appends_and_find_topic_reads_back(uid):
    import db
    db.load_topics(uid)  # seeds "workout" and "journal" at positions 0 and 1
    db.add_topic(uid, BOOKS)
    assert [t["slug"] for t in db.load_topics(uid)] == ["workout", "journal", "books"]
    found = db.find_topic(uid, "books")
    assert found["name"] == "Books"
    assert found["fields"][0]["label"] == "Author"
    assert db.find_topic(uid, "nope") is None


def test_topics_are_private_and_slugs_unique_per_user(uid, other):
    import db
    db.add_topic(uid, BOOKS)
    db.add_topic(other, {**BOOKS, "name": "Other Books"})  # same slug, no conflict
    assert db.find_topic(uid, "books")["name"] == "Books"
    assert db.find_topic(other, "books")["name"] == "Other Books"


def test_update_topic_updates_only_the_users_topic(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    updated = db.update_topic(uid, "workout", {"layout": "thumbnail", "name": "Jogs"})
    assert updated["layout"] == "thumbnail"
    assert updated["slug"] == "workout"
    assert db.find_topic(uid, "workout")["name"] == "Jogs"
    assert db.find_topic(other, "workout")["layout"] == "photo-top"
    assert db.update_topic(uid, "nope", {"layout": "thumbnail"}) is None


def test_delete_topic_cascades_entries_and_only_touches_the_users_topic(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "workout", {"id": 1, "date": "2026-07-09", "image": None})
    db.save_post(uid, "workout", 1, {"type": "doc", "content": []})
    db.delete_topic(uid, "workout")
    assert [t["slug"] for t in db.load_topics(uid)] == ["journal"]
    assert db.load_entries(uid, "workout") == []
    assert db.load_post(uid, "workout", 1) is None
    assert db.find_topic(other, "workout") is not None


def test_entry_round_trip_flattens_values(uid):
    import db
    db.load_topics(uid)
    assert db.next_entry_id(uid, "workout") == 1
    db.save_entry(uid, "workout", {"id": 1, "date": "2026-07-09", "image": None,
                                "title": "Run", "duration": 45})
    assert db.next_entry_id(uid, "workout") == 2
    got = db.find_entry(uid, "workout", 1)
    assert got == {"id": 1, "date": "2026-07-09", "image": None,
                   "title": "Run", "duration": 45}
    assert db.load_entries(uid, "workout") == [got]
    assert db.find_entry(uid, "workout", 999) is None


def test_entries_are_private_and_numbered_per_user(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "workout", {"id": 1, "date": "", "image": None, "title": "A's"})
    assert db.next_entry_id(other, "workout") == 1
    assert db.find_entry(other, "workout", 1) is None
    assert db.load_entries(other, "workout") == []
    db.save_entry(other, "workout", {"id": 1, "date": "", "image": None, "title": "B's"})
    assert db.find_entry(uid, "workout", 1)["title"] == "A's"
    assert db.find_entry(other, "workout", 1)["title"] == "B's"


def test_save_entry_upserts(uid):
    import db
    db.load_topics(uid)
    db.save_entry(uid, "workout", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    db.save_entry(uid, "workout", {"id": 1, "date": "2026-07-10", "image": None, "title": "B"})
    assert db.load_entries(uid, "workout") == [
        {"id": 1, "date": "2026-07-10", "image": None, "title": "B"}
    ]


def test_post_round_trip_and_absence(uid):
    import db
    db.load_topics(uid)
    db.save_entry(uid, "workout", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    assert db.load_post(uid, "workout", 1) is None
    doc = {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}]}
    db.save_post(uid, "workout", 1, doc)
    assert db.load_post(uid, "workout", 1) == doc
    doc2 = {"type": "doc", "content": []}
    db.save_post(uid, "workout", 1, doc2)  # upsert
    assert db.load_post(uid, "workout", 1) == doc2


def test_posts_are_private(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "workout", {"id": 1, "date": "", "image": None})
    db.save_entry(other, "workout", {"id": 1, "date": "", "image": None})
    db.save_post(uid, "workout", 1, {"type": "doc", "content": []})
    assert db.load_post(other, "workout", 1) is None


def test_delete_entry_removes_row_and_cascades_post(uid):
    import db
    db.load_topics(uid)
    db.save_entry(uid, "workout", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    db.save_post(uid, "workout", 1, {"type": "doc", "content": []})

    db.delete_entry(uid, "workout", 1)

    assert db.find_entry(uid, "workout", 1) is None
    assert db.load_post(uid, "workout", 1) is None  # FK cascade drops the posts row too


def test_delete_entry_is_a_no_op_for_unknown_or_other_users_entry(uid, other):
    import db
    db.load_topics(uid)
    db.save_entry(uid, "workout", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})

    db.delete_entry(uid, "workout", 999)
    db.delete_entry(other, "workout", 1)

    assert db.find_entry(uid, "workout", 1) is not None


def test_deleting_a_user_cascades_to_all_their_data(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "workout", {"id": 1, "date": "", "image": None})
    db.save_post(uid, "workout", 1, {"type": "doc", "content": []})
    db.save_entry(other, "workout", {"id": 1, "date": "", "image": None})

    db.get_conn().execute("delete from users where id=%s", (uid,))

    assert db.all_post_docs(uid) == []
    assert db.find_entry(other, "workout", 1) is not None


def test_all_entry_images_excludes_nulls_and_other_users(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.add_topic(uid, {**BOOKS, "fields": []})
    db.save_entry(uid, "workout", {"id": 1, "date": "", "image": "https://x/a.jpg"})
    db.save_entry(uid, "workout", {"id": 2, "date": "", "image": None})
    db.save_entry(uid, "books", {"id": 1, "date": "", "image": "https://x/b.jpg"})
    db.save_entry(other, "workout", {"id": 1, "date": "", "image": "https://x/c.jpg"})

    assert db.all_entry_images(uid) == {"https://x/a.jpg", "https://x/b.jpg"}


def test_all_post_docs_returns_only_this_users_docs(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "workout", {"id": 1, "date": "", "image": None})
    db.save_entry(other, "workout", {"id": 1, "date": "", "image": None})
    doc1 = {"type": "doc", "content": [{"type": "paragraph"}]}
    doc2 = {"type": "doc", "content": []}
    db.save_post(uid, "workout", 1, doc1)
    db.save_post(other, "workout", 1, doc2)

    assert db.all_post_docs(uid) == [doc1]


def test_upsert_user_creates_then_updates_by_google_sub(app_ctx):
    import db
    first = db.upsert_user("sub-1", "a@example.com", "A", None)
    again = db.upsert_user("sub-1", "a2@example.com", "A2", "https://pic/a")
    assert again == {"id": first["id"], "email": "a2@example.com", "name": "A2",
                     "avatar_url": "https://pic/a", "tips_seen": []}
    assert db.find_user(first["id"]) == again


def test_find_user_unknown_is_none(app_ctx):
    import db
    assert db.find_user(999999) is None


def test_mark_tips_seen_adds_each_tip_once(app_ctx):
    import db
    uid = db.upsert_user("sub-1", "a@example.com", None, None)["id"]
    assert db.mark_tips_seen(uid, ["log"])["tips_seen"] == ["log"]
    assert db.mark_tips_seen(uid, ["starter", "log"])["tips_seen"] == ["log", "starter"]
    assert db.find_user(uid)["tips_seen"] == ["log", "starter"]


def test_signing_in_again_keeps_seen_tips(app_ctx):
    import db
    uid = db.upsert_user("sub-1", "a@example.com", None, None)["id"]
    db.mark_tips_seen(uid, ["starter"])
    assert db.upsert_user("sub-1", "a@example.com", "A", None)["tips_seen"] == ["starter"]


def test_mark_tips_seen_for_a_missing_user_is_none(app_ctx):
    import db
    assert db.mark_tips_seen(999999, ["log"]) is None


# --- MCP grants ----------------------------------------------------------------

from datetime import timedelta  # noqa: E402


def age(column, grant_id, by):
    import db
    db.get_conn().execute(f"update mcp_grants set {column} = now() - %s where id=%s", (by, grant_id))


def test_grant_round_trip(uid):
    import db
    gid = db.create_grant(uid, "Claude", "claude.ai", "h" * 64)
    grant = db.find_grant(gid)
    assert (grant["user_id"], grant["client_name"], grant["redirect_host"], grant["secret_hash"]) == (
        uid, "Claude", "claude.ai", "h" * 64)
    assert grant["created_at"] is not None
    assert grant["redeemed_at"] is None and grant["last_used_at"] is None
    assert db.find_grant(gid + 1000) is None


def test_redeem_grant_succeeds_only_once(uid):
    import db
    gid = db.create_grant(uid, None, "claude.ai", "h")
    assert db.redeem_grant(gid) is True
    assert db.find_grant(gid)["redeemed_at"] is not None
    assert db.redeem_grant(gid) is False
    assert db.redeem_grant(gid + 1000) is False


def test_list_grants_shows_only_own_redeemed_grants_newest_first(uid, other):
    import db
    older = db.create_grant(uid, "Old", "claude.ai", "h")
    newer = db.create_grant(uid, "New", "chatgpt.com", "h")
    db.create_grant(uid, "Pending", "claude.ai", "h")  # never redeemed
    theirs = db.create_grant(other, "Theirs", "claude.ai", "h")
    for gid in (older, newer, theirs):
        db.redeem_grant(gid)
    age("created_at", older, timedelta(minutes=5))

    listed = db.list_grants(uid)
    assert [g["id"] for g in listed] == [newer, older]
    assert set(listed[0]) == {"id", "client_name", "redirect_host", "created_at", "last_used_at"}


def test_delete_grant_only_deletes_the_owners(uid, other):
    import db
    gid = db.create_grant(uid, None, "claude.ai", "h")
    assert db.delete_grant(other, gid) is False
    assert db.find_grant(gid) is not None
    assert db.delete_grant(uid, gid) is True
    assert db.find_grant(gid) is None
    assert db.delete_grant(uid, gid) is False


def test_touch_grant_writes_at_most_once_an_hour(uid):
    import db
    gid = db.create_grant(uid, None, "claude.ai", "h")
    db.touch_grant(gid)
    first = db.find_grant(gid)["last_used_at"]
    assert first is not None
    db.touch_grant(gid)
    assert db.find_grant(gid)["last_used_at"] == first
    age("last_used_at", gid, timedelta(hours=2))
    old = db.find_grant(gid)["last_used_at"]
    db.touch_grant(gid)
    assert db.find_grant(gid)["last_used_at"] > old


def test_create_grant_clears_abandoned_unredeemed_grants(uid, other):
    import db
    abandoned = db.create_grant(uid, None, "claude.ai", "h")
    recent = db.create_grant(uid, None, "claude.ai", "h")
    used = db.create_grant(uid, None, "claude.ai", "h")
    db.redeem_grant(used)
    theirs = db.create_grant(other, None, "claude.ai", "h")
    for gid in (abandoned, used, theirs):
        age("created_at", gid, timedelta(hours=2))

    db.create_grant(uid, None, "claude.ai", "h")
    assert db.find_grant(abandoned) is None
    assert db.find_grant(recent) is not None
    assert db.find_grant(used) is not None
    assert db.find_grant(theirs) is not None  # another user's are left alone


def test_deleting_a_user_deletes_their_grants(uid):
    import db
    gid = db.create_grant(uid, None, "claude.ai", "h")
    db.get_conn().execute("delete from users where id=%s", (uid,))
    assert db.find_grant(gid) is None


def test_update_topic_fields_strips_removed_values_from_that_topic_only(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.add_topic(uid, {"slug": "swims", "name": "Swims", "color": "blue",
                       "layout": "photo-top",
                       "fields": [{"key": "duration", "label": "Duration",
                                   "type": "number", "direction": "higher"}]})
    for user in (uid, other):
        db.save_entry(user, "workout", {"id": 1, "date": "", "image": None,
                                        "title": "A", "duration": 30})
    db.save_entry(uid, "swims", {"id": 1, "date": "", "image": None, "duration": 5})

    title_only = [{"key": "title", "label": "Title", "type": "text", "direction": "none"}]
    updated = db.update_topic(uid, "workout", {"fields": title_only},
                              removed_keys=["duration"])

    assert updated["fields"] == title_only
    mine = db.find_entry(uid, "workout", 1)
    assert "duration" not in mine and mine["title"] == "A"
    assert db.find_entry(other, "workout", 1)["duration"] == 30
    assert db.find_entry(uid, "swims", 1)["duration"] == 5
