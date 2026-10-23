"""The columns analytics reads straight from the database: when and how each
entry was logged, where each user first came from, and when they were last
seen. See backend/analytics.sql for the queries."""
import os

import psycopg
from psycopg.rows import dict_row

from conftest import make_grant
from test_auth import google, sign_in  # noqa: F401  (google is a fixture)

MIGRATION_PATH = os.path.join(os.path.dirname(__file__), "migrations", "006_analytics.sql")


def query(test_db, sql, *params):
    with psycopg.connect(test_db, row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def make_topic(c, headers=None):
    res = c.post("/api/topics", json={"name": "Runs", "fields": []}, headers=headers)
    assert res.status_code == 201
    return res.get_json()["slug"]


def me_id(c):
    return c.get("/api/auth/me").get_json()["user"]["id"]


def test_an_entry_logged_in_the_browser_is_marked_web(client, test_db):
    slug = make_topic(client)
    client.post(f"/api/topics/{slug}/entries", json={"date": "2026-01-01"})
    [row] = query(test_db, "select via, created_at from entries")
    assert row["via"] == "web"
    assert row["created_at"] is not None


def test_an_entry_logged_by_a_connected_app_is_marked_mcp(client, test_db):
    _, credential = make_grant(me_id(client))
    app_headers = {"Authorization": f"Bearer {credential}"}
    with client.session_transaction() as s:
        s.clear()  # only the app's credential, as the MCP server sends it
    slug = make_topic(client, app_headers)
    res = client.post(f"/api/topics/{slug}/entries", json={}, headers=app_headers)
    assert res.status_code == 201
    [row] = query(test_db, "select via from entries")
    assert row["via"] == "mcp"


def test_editing_an_entry_keeps_how_and_when_it_was_logged(client, test_db):
    _, credential = make_grant(me_id(client))
    app_headers = {"Authorization": f"Bearer {credential}"}
    slug = make_topic(client)
    with client.session_transaction() as s:
        uid = s["user_id"]
        s.clear()
    client.post(f"/api/topics/{slug}/entries", json={}, headers=app_headers)
    [before] = query(test_db, "select via, created_at from entries")
    with client.session_transaction() as s:
        s["user_id"] = uid
    assert client.patch(f"/api/topics/{slug}/entries/1", json={"date": "x"}).status_code == 200
    [after] = query(test_db, "select via, created_at, date from entries")
    assert after["date"] == "x"
    assert (after["via"], after["created_at"]) == ("mcp", before["created_at"])


def test_sign_up_records_where_the_person_came_from(db_anon_client, google, test_db):  # noqa: F811
    db_anon_client.get("/api/auth/google", query_string={"next": "/", "src": "twitter"})
    db_anon_client.get("/api/auth/google/callback?code=x&state=y")
    [row] = query(test_db, "select signup_source from users")
    assert row["signup_source"] == "twitter"


def test_signing_in_again_keeps_the_original_source(db_anon_client, google, test_db):  # noqa: F811
    db_anon_client.get("/api/auth/google", query_string={"src": "twitter"})
    db_anon_client.get("/api/auth/google/callback?code=x&state=y")
    db_anon_client.get("/api/auth/google", query_string={"src": "t.co"})
    db_anon_client.get("/api/auth/google/callback?code=x&state=y")
    [row] = query(test_db, "select signup_source from users")
    assert row["signup_source"] == "twitter"


def test_sign_up_without_a_source_leaves_it_empty(db_anon_client, google, test_db):  # noqa: F811
    sign_in(db_anon_client)
    [row] = query(test_db, "select signup_source from users")
    assert row["signup_source"] is None


def test_a_junk_source_is_trimmed_or_dropped(db_anon_client, google, test_db):  # noqa: F811
    db_anon_client.get("/api/auth/google", query_string={"src": "x" * 500})
    db_anon_client.get("/api/auth/google/callback?code=x&state=y")
    [row] = query(test_db, "select signup_source from users")
    assert row["signup_source"] == "x" * 100

    google.user["sub"] = "g-456"
    db_anon_client.get("/api/auth/google", query_string={"src": "bad\nsource"})
    db_anon_client.get("/api/auth/google/callback?code=x&state=y")
    rows = query(test_db, "select signup_source from users where google_sub='g-456'")
    assert rows[0]["signup_source"] is None


def test_signing_in_records_when_the_person_was_last_seen(db_anon_client, google, test_db):  # noqa: F811
    sign_in(db_anon_client)
    [row] = query(test_db, "select last_seen_at from users")
    assert row["last_seen_at"] is not None


def test_opening_the_app_refreshes_last_seen(client, test_db):
    query(test_db, "update users set last_seen_at = now() - interval '3 days' returning id")
    assert client.get("/api/auth/me").status_code == 200
    [row] = query(test_db, "select last_seen_at > now() - interval '1 minute' as fresh from users")
    assert row["fresh"]


def test_migration_adds_the_columns_and_is_safe_to_rerun(test_db):
    with psycopg.connect(test_db, autocommit=True) as conn:
        conn.execute("alter table entries drop column created_at, drop column via")
        conn.execute("alter table users drop column signup_source, drop column last_seen_at")
        with open(MIGRATION_PATH) as f:
            sql = f.read()
        conn.execute(sql)
        conn.execute(sql)
    cols = query(
        test_db,
        "select table_name || '.' || column_name as c from information_schema.columns "
        "where column_name in ('created_at', 'via', 'signup_source', 'last_seen_at') "
        "and table_name in ('entries', 'users') order by 1",
    )
    assert [r["c"] for r in cols] == [
        "entries.created_at", "entries.via", "users.created_at",
        "users.last_seen_at", "users.signup_source",
    ]
