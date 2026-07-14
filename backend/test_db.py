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
