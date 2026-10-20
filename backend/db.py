import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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


def _seed_if_empty(conn, user_id):
    """Give a user the default topics the first time they have none."""
    if conn.execute(
        "select count(*) as c from topics where user_id=%s", (user_id,)
    ).fetchone()["c"]:
        return
    for pos, t in enumerate(DEFAULT_TOPICS):
        conn.execute(
            "insert into topics (user_id, slug, name, color, layout, fields, position) "
            "values (%s, %s, %s, %s, %s, %s, %s) on conflict (user_id, slug) do nothing",
            (user_id, t["slug"], t["name"], t["color"], t["layout"],
             Jsonb(t["fields"]), pos),
        )


def load_topics(user_id):
    conn = get_conn()
    _seed_if_empty(conn, user_id)
    rows = conn.execute(
        "select slug, name, color, layout, fields from topics "
        "where user_id=%s order by position",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def find_topic(user_id, slug):
    return next((t for t in load_topics(user_id) if t["slug"] == slug), None)


def add_topic(user_id, topic):
    conn = get_conn()
    pos = conn.execute(
        "select coalesce(max(position), -1) + 1 as p from topics where user_id=%s",
        (user_id,),
    ).fetchone()["p"]
    conn.execute(
        "insert into topics (user_id, slug, name, color, layout, fields, position) "
        "values (%s, %s, %s, %s, %s, %s, %s)",
        (user_id, topic["slug"], topic["name"], topic["color"], topic["layout"],
         Jsonb(topic["fields"]), pos),
    )


TOPIC_EDITABLE = ("name", "color", "layout")


def update_topic(user_id, slug, changes):
    """Apply changes (a subset of TOPIC_EDITABLE) to one topic. The slug never
    changes, so entry URLs stay stable across a rename."""
    cols = [c for c in TOPIC_EDITABLE if c in changes]
    if not cols:
        return find_topic(user_id, slug)
    conn = get_conn()
    row = conn.execute(
        "update topics set " + ", ".join(f"{c}=%s" for c in cols) +
        " where user_id=%s and slug=%s returning slug, name, color, layout, fields",
        (*[changes[c] for c in cols], user_id, slug),
    ).fetchone()
    return dict(row) if row else None


def delete_topic(user_id, slug):
    """Its entries and their posts go with it via the FKs' on delete cascade."""
    get_conn().execute(
        "delete from topics where user_id=%s and slug=%s", (user_id, slug)
    )


def _flatten(row):
    entry = {"id": row["id"], "date": row["date"], "image": row["image"]}
    entry.update(row["values"] or {})
    return entry


def count_entries(user_id):
    """All of a user's entries, across every topic."""
    conn = get_conn()
    return conn.execute(
        "select count(*) as c from entries where user_id=%s", (user_id,)
    ).fetchone()["c"]


def next_entry_id(user_id, slug):
    conn = get_conn()
    return conn.execute(
        "select coalesce(max(id), 0) + 1 as next from entries "
        "where user_id=%s and topic_slug=%s",
        (user_id, slug),
    ).fetchone()["next"]


def load_entries(user_id, slug):
    conn = get_conn()
    rows = conn.execute(
        'select id, date, image, "values" from entries '
        "where user_id=%s and topic_slug=%s order by id",
        (user_id, slug),
    ).fetchall()
    return [_flatten(r) for r in rows]


def find_entry(user_id, slug, entry_id):
    conn = get_conn()
    row = conn.execute(
        'select id, date, image, "values" from entries '
        "where user_id=%s and topic_slug=%s and id=%s",
        (user_id, slug, entry_id),
    ).fetchone()
    return _flatten(row) if row else None


def save_entry(user_id, slug, entry):
    values = {k: v for k, v in entry.items()
              if k not in ("id", "date", "image", "body")}
    conn = get_conn()
    conn.execute(
        'insert into entries (user_id, topic_slug, id, date, image, "values") '
        "values (%s, %s, %s, %s, %s, %s) "
        "on conflict (user_id, topic_slug, id) do update set "
        'date = excluded.date, image = excluded.image, "values" = excluded."values"',
        (user_id, slug, entry["id"], entry.get("date", ""), entry.get("image"),
         Jsonb(values)),
    )


def load_post(user_id, slug, entry_id):
    conn = get_conn()
    row = conn.execute(
        "select doc from posts where user_id=%s and topic_slug=%s and entry_id=%s",
        (user_id, slug, entry_id),
    ).fetchone()
    return row["doc"] if row else None


def save_post(user_id, slug, entry_id, doc):
    conn = get_conn()
    conn.execute(
        "insert into posts (user_id, topic_slug, entry_id, doc) values (%s, %s, %s, %s) "
        "on conflict (user_id, topic_slug, entry_id) do update set doc = excluded.doc",
        (user_id, slug, entry_id, Jsonb(doc)),
    )


def delete_entry(user_id, slug, entry_id):
    """The posts row (if any) goes with it via the FK's on delete cascade."""
    conn = get_conn()
    conn.execute(
        "delete from entries where user_id=%s and topic_slug=%s and id=%s",
        (user_id, slug, entry_id),
    )


# Each user's objects live under their own storage prefix, so only their own
# rows can still reference them (see app.delete_entry).
def all_entry_images(user_id):
    conn = get_conn()
    rows = conn.execute(
        "select image from entries where user_id=%s and image is not null", (user_id,)
    ).fetchall()
    return {r["image"] for r in rows}


def all_post_docs(user_id):
    conn = get_conn()
    rows = conn.execute("select doc from posts where user_id=%s", (user_id,)).fetchall()
    return [r["doc"] for r in rows]


def topic_post_docs(user_id, slug):
    conn = get_conn()
    rows = conn.execute(
        "select doc from posts where user_id=%s and topic_slug=%s", (user_id, slug)
    ).fetchall()
    return [r["doc"] for r in rows]


# --- Users -------------------------------------------------------------------

USER_COLUMNS = "id, email, name, avatar_url"


def upsert_user(google_sub, email, name, avatar_url):
    """Create the user on first sign-in; refresh their profile on later ones.

    Keyed by Google's stable `sub`, not email, since an account's email can
    change.
    """
    row = get_conn().execute(
        "insert into users (google_sub, email, name, avatar_url) "
        "values (%s, %s, %s, %s) "
        "on conflict (google_sub) do update set email = excluded.email, "
        "name = excluded.name, avatar_url = excluded.avatar_url "
        f"returning {USER_COLUMNS}",
        (google_sub, email, name, avatar_url),
    ).fetchone()
    return dict(row)


def find_user(user_id):
    row = get_conn().execute(
        f"select {USER_COLUMNS} from users where id=%s", (user_id,)
    ).fetchone()
    return dict(row) if row else None


# --- MCP grants --------------------------------------------------------------

GRANT_COLUMNS = (
    "id, user_id, client_name, redirect_host, secret_hash, "
    "created_at, redeemed_at, last_used_at"
)


def create_grant(user_id, client_name, redirect_host, secret_hash):
    """Store a not-yet-redeemed grant and return its id.

    Also drops this user's grants that were never redeemed and are over an
    hour old: their code expired long ago, so nothing can redeem them.
    """
    conn = get_conn()
    conn.execute(
        "delete from mcp_grants where user_id=%s and redeemed_at is null "
        "and created_at < now() - interval '1 hour'",
        (user_id,),
    )
    return conn.execute(
        "insert into mcp_grants (user_id, client_name, redirect_host, secret_hash) "
        "values (%s, %s, %s, %s) returning id",
        (user_id, client_name, redirect_host, secret_hash),
    ).fetchone()["id"]


def find_grant(grant_id):
    row = get_conn().execute(
        f"select {GRANT_COLUMNS} from mcp_grants where id=%s", (grant_id,)
    ).fetchone()
    return dict(row) if row else None


def redeem_grant(grant_id):
    """Mark the grant redeemed. False if it already was (or is gone); one
    statement, so two racing code exchanges can't both win."""
    row = get_conn().execute(
        "update mcp_grants set redeemed_at = now() "
        "where id=%s and redeemed_at is null returning id",
        (grant_id,),
    ).fetchone()
    return row is not None


def touch_grant(grant_id):
    """Record a use, at most once an hour, rather than a write per API call."""
    get_conn().execute(
        "update mcp_grants set last_used_at = now() where id=%s "
        "and (last_used_at is null or last_used_at < now() - interval '1 hour')",
        (grant_id,),
    )


def list_grants(user_id):
    """The user's connected apps. Unredeemed grants are connections that
    never finished, so they aren't shown."""
    rows = get_conn().execute(
        "select id, client_name, redirect_host, created_at, last_used_at "
        "from mcp_grants where user_id=%s and redeemed_at is not null "
        "order by created_at desc, id desc",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_grant(user_id, grant_id):
    """Delete one of user_id's grants. False if there was no such grant."""
    cur = get_conn().execute(
        "delete from mcp_grants where id=%s and user_id=%s", (grant_id, user_id)
    )
    return cur.rowcount > 0
