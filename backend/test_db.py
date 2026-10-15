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


def test_seeds_default_runs_topic_when_the_user_has_none(uid):
    import db
    topics = db.load_topics(uid)
    assert [t["slug"] for t in topics] == ["runs"]
    assert topics[0]["fields"][0]["key"] == "title"


def test_seeding_is_per_user(uid, other):
    import db
    db.add_topic(uid, BOOKS)  # uid now has topics, so no seed for uid
    assert [t["slug"] for t in db.load_topics(uid)] == ["books"]
    assert [t["slug"] for t in db.load_topics(other)] == ["runs"]


def test_add_topic_appends_and_find_topic_reads_back(uid):
    import db
    db.load_topics(uid)  # seeds "runs" at position 0
    db.add_topic(uid, BOOKS)
    assert [t["slug"] for t in db.load_topics(uid)] == ["runs", "books"]
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


def test_set_topic_layout_updates_only_the_users_topic(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    updated = db.set_topic_layout(uid, "runs", "thumbnail")
    assert updated["layout"] == "thumbnail"
    assert db.find_topic(uid, "runs")["layout"] == "thumbnail"
    assert db.find_topic(other, "runs")["layout"] == "photo-top"
    assert db.set_topic_layout(uid, "nope", "thumbnail") is None


def test_entry_round_trip_flattens_values(uid):
    import db
    db.load_topics(uid)
    assert db.next_entry_id(uid, "runs") == 1
    db.save_entry(uid, "runs", {"id": 1, "date": "2026-07-09", "image": None,
                                "title": "Run", "distance": 5.25})
    assert db.next_entry_id(uid, "runs") == 2
    got = db.find_entry(uid, "runs", 1)
    assert got == {"id": 1, "date": "2026-07-09", "image": None,
                   "title": "Run", "distance": 5.25}
    assert db.load_entries(uid, "runs") == [got]
    assert db.find_entry(uid, "runs", 999) is None


def test_entries_are_private_and_numbered_per_user(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "runs", {"id": 1, "date": "", "image": None, "title": "A's"})
    assert db.next_entry_id(other, "runs") == 1
    assert db.find_entry(other, "runs", 1) is None
    assert db.load_entries(other, "runs") == []
    db.save_entry(other, "runs", {"id": 1, "date": "", "image": None, "title": "B's"})
    assert db.find_entry(uid, "runs", 1)["title"] == "A's"
    assert db.find_entry(other, "runs", 1)["title"] == "B's"


def test_save_entry_upserts(uid):
    import db
    db.load_topics(uid)
    db.save_entry(uid, "runs", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    db.save_entry(uid, "runs", {"id": 1, "date": "2026-07-10", "image": None, "title": "B"})
    assert db.load_entries(uid, "runs") == [
        {"id": 1, "date": "2026-07-10", "image": None, "title": "B"}
    ]


def test_post_round_trip_and_absence(uid):
    import db
    db.load_topics(uid)
    db.save_entry(uid, "runs", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    assert db.load_post(uid, "runs", 1) is None
    doc = {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}]}
    db.save_post(uid, "runs", 1, doc)
    assert db.load_post(uid, "runs", 1) == doc
    doc2 = {"type": "doc", "content": []}
    db.save_post(uid, "runs", 1, doc2)  # upsert
    assert db.load_post(uid, "runs", 1) == doc2


def test_posts_are_private(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "runs", {"id": 1, "date": "", "image": None})
    db.save_entry(other, "runs", {"id": 1, "date": "", "image": None})
    db.save_post(uid, "runs", 1, {"type": "doc", "content": []})
    assert db.load_post(other, "runs", 1) is None


def test_delete_entry_removes_row_and_cascades_post(uid):
    import db
    db.load_topics(uid)
    db.save_entry(uid, "runs", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    db.save_post(uid, "runs", 1, {"type": "doc", "content": []})

    db.delete_entry(uid, "runs", 1)

    assert db.find_entry(uid, "runs", 1) is None
    assert db.load_post(uid, "runs", 1) is None  # FK cascade drops the posts row too


def test_delete_entry_is_a_no_op_for_unknown_or_other_users_entry(uid, other):
    import db
    db.load_topics(uid)
    db.save_entry(uid, "runs", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})

    db.delete_entry(uid, "runs", 999)
    db.delete_entry(other, "runs", 1)

    assert db.find_entry(uid, "runs", 1) is not None


def test_deleting_a_user_cascades_to_all_their_data(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "runs", {"id": 1, "date": "", "image": None})
    db.save_post(uid, "runs", 1, {"type": "doc", "content": []})
    db.save_entry(other, "runs", {"id": 1, "date": "", "image": None})

    db.get_conn().execute("delete from users where id=%s", (uid,))

    assert db.all_post_docs(uid) == []
    assert db.find_entry(other, "runs", 1) is not None


def test_all_entry_images_excludes_nulls_and_other_users(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.add_topic(uid, {**BOOKS, "fields": []})
    db.save_entry(uid, "runs", {"id": 1, "date": "", "image": "https://x/a.jpg"})
    db.save_entry(uid, "runs", {"id": 2, "date": "", "image": None})
    db.save_entry(uid, "books", {"id": 1, "date": "", "image": "https://x/b.jpg"})
    db.save_entry(other, "runs", {"id": 1, "date": "", "image": "https://x/c.jpg"})

    assert db.all_entry_images(uid) == {"https://x/a.jpg", "https://x/b.jpg"}


def test_all_post_docs_returns_only_this_users_docs(uid, other):
    import db
    db.load_topics(uid)
    db.load_topics(other)
    db.save_entry(uid, "runs", {"id": 1, "date": "", "image": None})
    db.save_entry(other, "runs", {"id": 1, "date": "", "image": None})
    doc1 = {"type": "doc", "content": [{"type": "paragraph"}]}
    doc2 = {"type": "doc", "content": []}
    db.save_post(uid, "runs", 1, doc1)
    db.save_post(other, "runs", 1, doc2)

    assert db.all_post_docs(uid) == [doc1]


def test_upsert_user_creates_then_updates_by_google_sub(app_ctx):
    import db
    first = db.upsert_user("sub-1", "a@example.com", "A", None)
    again = db.upsert_user("sub-1", "a2@example.com", "A2", "https://pic/a")
    assert again == {"id": first["id"], "email": "a2@example.com", "name": "A2",
                     "avatar_url": "https://pic/a"}
    assert db.find_user(first["id"]) == again


def test_find_user_unknown_is_none(app_ctx):
    import db
    assert db.find_user(999999) is None
