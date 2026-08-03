def test_get_conn_can_query_the_schema(app_ctx):
    import db
    conn = db.get_conn()
    rows = conn.execute(
        "select table_name from information_schema.tables "
        "where table_schema='public' order by table_name"
    ).fetchall()
    names = {r["table_name"] for r in rows}
    assert {"topics", "entries", "posts"} <= names


def test_seeds_default_runs_topic_when_empty(app_ctx):
    import db
    topics = db.load_topics()
    assert [t["slug"] for t in topics] == ["runs"]
    assert topics[0]["fields"][0]["key"] == "title"


def test_add_topic_appends_and_find_topic_reads_back(app_ctx):
    import db
    db.load_topics()  # seeds "runs" at position 0
    db.add_topic({
        "slug": "books", "name": "Books", "color": "red", "layout": "photo-top",
        "fields": [{"key": "author", "label": "Author", "type": "text", "direction": "none"}],
    })
    assert [t["slug"] for t in db.load_topics()] == ["runs", "books"]
    found = db.find_topic("books")
    assert found["name"] == "Books"
    assert found["fields"][0]["label"] == "Author"
    assert db.find_topic("nope") is None


def test_set_topic_layout_updates(app_ctx):
    import db
    db.load_topics()
    updated = db.set_topic_layout("runs", "thumbnail")
    assert updated["layout"] == "thumbnail"
    assert db.find_topic("runs")["layout"] == "thumbnail"
    assert db.set_topic_layout("nope", "thumbnail") is None


def _seed_runs(db):
    db.load_topics()  # ensures the "runs" topic exists


def test_entry_round_trip_flattens_values(app_ctx):
    import db
    _seed_runs(db)
    assert db.next_entry_id("runs") == 1
    db.save_entry("runs", {"id": 1, "date": "2026-07-09", "image": None,
                           "title": "Run", "distance": 5.25})
    assert db.next_entry_id("runs") == 2
    got = db.find_entry("runs", 1)
    assert got == {"id": 1, "date": "2026-07-09", "image": None,
                   "title": "Run", "distance": 5.25}
    assert db.load_entries("runs") == [got]
    assert db.find_entry("runs", 999) is None


def test_save_entry_upserts(app_ctx):
    import db
    _seed_runs(db)
    db.save_entry("runs", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    db.save_entry("runs", {"id": 1, "date": "2026-07-10", "image": None, "title": "B"})
    assert db.load_entries("runs") == [
        {"id": 1, "date": "2026-07-10", "image": None, "title": "B"}
    ]


def test_post_round_trip_and_absence(app_ctx):
    import db
    _seed_runs(db)
    db.save_entry("runs", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    assert db.load_post("runs", 1) is None
    doc = {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}]}
    db.save_post("runs", 1, doc)
    assert db.load_post("runs", 1) == doc
    doc2 = {"type": "doc", "content": []}
    db.save_post("runs", 1, doc2)  # upsert
    assert db.load_post("runs", 1) == doc2


def test_delete_entry_removes_row_and_cascades_post(app_ctx):
    import db
    _seed_runs(db)
    db.save_entry("runs", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})
    db.save_post("runs", 1, {"type": "doc", "content": []})

    db.delete_entry("runs", 1)

    assert db.find_entry("runs", 1) is None
    assert db.load_post("runs", 1) is None  # FK cascade drops the posts row too


def test_delete_entry_is_a_no_op_for_unknown_entry(app_ctx):
    import db
    _seed_runs(db)
    db.save_entry("runs", {"id": 1, "date": "2026-07-09", "image": None, "title": "A"})

    db.delete_entry("runs", 999)  # no matching row in this topic

    assert db.find_entry("runs", 1) is not None  # the real entry survives untouched


def test_all_entry_images_excludes_nulls_across_topics(app_ctx):
    import db
    _seed_runs(db)
    db.add_topic({"slug": "books", "name": "Books", "color": "red", "layout": "photo-top",
                  "fields": []})
    db.save_entry("runs", {"id": 1, "date": "", "image": "https://x/a.jpg"})
    db.save_entry("runs", {"id": 2, "date": "", "image": None})
    db.save_entry("books", {"id": 1, "date": "", "image": "https://x/b.jpg"})

    assert db.all_entry_images() == {"https://x/a.jpg", "https://x/b.jpg"}


def test_all_post_docs_returns_every_doc(app_ctx):
    import db
    _seed_runs(db)
    db.save_entry("runs", {"id": 1, "date": "", "image": None})
    db.save_entry("runs", {"id": 2, "date": "", "image": None})
    doc1 = {"type": "doc", "content": [{"type": "paragraph"}]}
    doc2 = {"type": "doc", "content": []}
    db.save_post("runs", 1, doc1)
    db.save_post("runs", 2, doc2)

    docs = db.all_post_docs()
    assert len(docs) == 2
    assert doc1 in docs
    assert doc2 in docs
