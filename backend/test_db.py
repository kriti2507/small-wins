def test_get_conn_can_query_the_schema(app_ctx):
    import db
    conn = db.get_conn()
    rows = conn.execute(
        "select table_name from information_schema.tables "
        "where table_schema='public' order by table_name"
    ).fetchall()
    names = {r["table_name"] for r in rows}
    assert {"topics", "entries", "posts"} <= names
