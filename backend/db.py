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


def _flatten(row):
    entry = {"id": row["id"], "date": row["date"], "image": row["image"]}
    entry.update(row["values"] or {})
    return entry


def next_entry_id(slug):
    conn = get_conn()
    return conn.execute(
        "select coalesce(max(id), 0) + 1 as next from entries where topic_slug=%s",
        (slug,),
    ).fetchone()["next"]


def load_entries(slug):
    conn = get_conn()
    rows = conn.execute(
        'select id, date, image, "values" from entries where topic_slug=%s order by id',
        (slug,),
    ).fetchall()
    return [_flatten(r) for r in rows]


def find_entry(slug, entry_id):
    conn = get_conn()
    row = conn.execute(
        'select id, date, image, "values" from entries where topic_slug=%s and id=%s',
        (slug, entry_id),
    ).fetchone()
    return _flatten(row) if row else None


def save_entry(slug, entry):
    values = {k: v for k, v in entry.items()
              if k not in ("id", "date", "image", "body")}
    conn = get_conn()
    conn.execute(
        'insert into entries (topic_slug, id, date, image, "values") '
        'values (%s, %s, %s, %s, %s) '
        'on conflict (topic_slug, id) do update set '
        'date = excluded.date, image = excluded.image, "values" = excluded."values"',
        (slug, entry["id"], entry.get("date", ""), entry.get("image"), Jsonb(values)),
    )


def load_post(slug, entry_id):
    conn = get_conn()
    row = conn.execute(
        "select doc from posts where topic_slug=%s and entry_id=%s",
        (slug, entry_id),
    ).fetchone()
    return row["doc"] if row else None


def save_post(slug, entry_id, doc):
    conn = get_conn()
    conn.execute(
        "insert into posts (topic_slug, entry_id, doc) values (%s, %s, %s) "
        "on conflict (topic_slug, entry_id) do update set doc = excluded.doc",
        (slug, entry_id, Jsonb(doc)),
    )


def delete_entry(slug, entry_id):
    """The posts row (if any) goes with it via the FK's on delete cascade."""
    conn = get_conn()
    conn.execute(
        "delete from entries where topic_slug=%s and id=%s",
        (slug, entry_id),
    )


def all_entry_images():
    conn = get_conn()
    rows = conn.execute(
        "select image from entries where image is not null"
    ).fetchall()
    return {r["image"] for r in rows}


def all_post_docs():
    conn = get_conn()
    rows = conn.execute("select doc from posts").fetchall()
    return [r["doc"] for r in rows]
