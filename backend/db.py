import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb  # noqa: F401  (used by later tasks)

# Read at call time so tests can monkeypatch db.DATABASE_URL (mirrors the
# file-storage era, where module globals were monkeypatched in tests).
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    """A psycopg connection, cached on Flask's request context when there is
    one, else standalone (scripts/tests inside an app context).

    prepare_threshold=None disables prepared statements (required by Supabase's
    transaction-mode pooler). autocommit keeps each statement self-contained,
    which is all this app needs.
    """
    from flask import g, has_app_context

    if has_app_context():
        if "db_conn" not in g:
            g.db_conn = psycopg.connect(
                DATABASE_URL, autocommit=True, prepare_threshold=None,
                row_factory=dict_row,
            )
        return g.db_conn
    return psycopg.connect(
        DATABASE_URL, autocommit=True, prepare_threshold=None, row_factory=dict_row
    )


DEFAULT_TOPICS = [
    {
        "slug": "runs",
        "name": "Runs",
        "color": "green",
        "layout": "photo-top",
        "fields": [
            {"key": "title", "label": "Title", "type": "text", "direction": "none"},
            {"key": "distance", "label": "Distance (km)", "type": "number", "direction": "higher"},
            {"key": "pace", "label": "Pace", "type": "pace", "direction": "lower"},
            {"key": "heart_rate", "label": "Heart rate (bpm)", "type": "number", "direction": "none"},
        ],
    }
]


def _seed_if_empty(conn):
    if conn.execute("select count(*) as c from topics").fetchone()["c"]:
        return
    for pos, t in enumerate(DEFAULT_TOPICS):
        conn.execute(
            "insert into topics (slug, name, color, layout, fields, position) "
            "values (%s, %s, %s, %s, %s, %s) on conflict (slug) do nothing",
            (t["slug"], t["name"], t["color"], t["layout"], Jsonb(t["fields"]), pos),
        )


def load_topics():
    conn = get_conn()
    _seed_if_empty(conn)
    rows = conn.execute(
        "select slug, name, color, layout, fields from topics order by position"
    ).fetchall()
    return [dict(r) for r in rows]


def find_topic(slug):
    return next((t for t in load_topics() if t["slug"] == slug), None)


def add_topic(topic):
    conn = get_conn()
    pos = conn.execute(
        "select coalesce(max(position), -1) + 1 as p from topics"
    ).fetchone()["p"]
    conn.execute(
        "insert into topics (slug, name, color, layout, fields, position) "
        "values (%s, %s, %s, %s, %s, %s)",
        (topic["slug"], topic["name"], topic["color"], topic["layout"],
         Jsonb(topic["fields"]), pos),
    )


def set_topic_layout(slug, layout):
    conn = get_conn()
    row = conn.execute(
        "update topics set layout=%s where slug=%s "
        "returning slug, name, color, layout, fields",
        (layout, slug),
    ).fetchone()
    return dict(row) if row else None
