"""Runs migrations/002_user_scoping.sql against the pre-Phase-2 tables.

Uses its own Postgres schema (via search_path) so the shared test tables
from conftest are untouched.
"""
import os

import psycopg
import pytest

MIGRATION = os.path.join(os.path.dirname(__file__), "migrations", "002_user_scoping.sql")
PLACEHOLDER = "'you@example.com'"

# backend/schema.sql as it was before Phase 2 (what production has today).
OLD_SCHEMA = """
create table topics (
  slug     text primary key,
  name     text not null,
  color    text not null,
  layout   text not null,
  fields   jsonb not null default '[]'::jsonb,
  position integer not null
);
create table entries (
  topic_slug text    not null references topics(slug) on delete cascade,
  id         integer not null,
  date       text    not null default '',
  image      text,
  "values"   jsonb   not null default '{}'::jsonb,
  primary key (topic_slug, id)
);
create table posts (
  topic_slug text    not null,
  entry_id   integer not null,
  doc        jsonb   not null,
  primary key (topic_slug, entry_id),
  foreign key (topic_slug, entry_id) references entries(topic_slug, id) on delete cascade
);
create table users (
  id          bigserial primary key,
  google_sub  text unique not null,
  email       text not null,
  name        text,
  avatar_url  text,
  created_at  timestamptz not null default now()
);
"""


@pytest.fixture()
def old_db(_schema):
    with psycopg.connect(_schema, autocommit=True) as conn:
        conn.execute("drop schema if exists phase2_mig cascade")
        conn.execute("create schema phase2_mig")
        conn.execute("set search_path to phase2_mig")
        conn.execute(OLD_SCHEMA)
        yield conn
        conn.execute("drop schema phase2_mig cascade")


def migration_for(email):
    with open(MIGRATION) as f:
        sql = f.read()
    assert sql.count(PLACEHOLDER) == 1, "the owner email must appear exactly once"
    return sql.replace(PLACEHOLDER, f"'{email}'")


def seed(conn):
    """Old-layout data plus two users; returns (owner_id, friend_id)."""
    owner = conn.execute(
        "insert into users (google_sub, email) values ('g-1', 'Me@Example.com') returning id"
    ).fetchone()[0]
    friend = conn.execute(
        "insert into users (google_sub, email) values ('g-2', 'friend@example.com') returning id"
    ).fetchone()[0]
    conn.execute("insert into topics (slug, name, color, layout, position) "
                 "values ('runs', 'Runs', 'green', 'photo-top', 0)")
    conn.execute("insert into entries (topic_slug, id, date) values ('runs', 1, '2026-01-01')")
    conn.execute("insert into posts (topic_slug, entry_id, doc) "
                 """values ('runs', 1, '{"type": "doc"}')""")
    return owner, friend


def columns(conn, table):
    rows = conn.execute(
        "select column_name, is_nullable from information_schema.columns "
        "where table_schema = 'phase2_mig' and table_name = %s", (table,)
    ).fetchall()
    return dict(rows)


def test_assigns_every_row_to_the_owner_case_insensitively(old_db):
    owner, _ = seed(old_db)
    old_db.execute(migration_for("me@example.com"))
    for table in ("topics", "entries", "posts"):
        assert columns(old_db, table)["user_id"] == "NO", table
        owners = old_db.execute(f"select array_agg(distinct user_id) from {table}").fetchone()[0]
        assert owners == [owner], table


def test_slugs_and_entry_ids_become_per_user(old_db):
    _, friend = seed(old_db)
    old_db.execute(migration_for("me@example.com"))
    old_db.execute("insert into topics (user_id, slug, name, color, layout, position) "
                   "values (%s, 'runs', 'Runs', 'green', 'photo-top', 0)", (friend,))
    old_db.execute("insert into entries (user_id, topic_slug, id) values (%s, 'runs', 1)", (friend,))
    assert old_db.execute("select count(*) from entries").fetchone()[0] == 2


def test_entries_must_belong_to_their_users_topic(old_db):
    _, friend = seed(old_db)
    old_db.execute(migration_for("me@example.com"))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        old_db.execute("insert into entries (user_id, topic_slug, id) values (%s, 'runs', 2)", (friend,))


def test_cascades_still_work(old_db):
    owner, _ = seed(old_db)
    old_db.execute(migration_for("me@example.com"))
    old_db.execute("delete from users where id = %s", (owner,))
    for table in ("topics", "entries", "posts"):
        assert old_db.execute(f"select count(*) from {table}").fetchone()[0] == 0, table


def test_unknown_owner_email_changes_nothing(old_db):
    seed(old_db)
    with pytest.raises(psycopg.errors.RaiseException, match="nobody@example.com"):
        old_db.execute(migration_for("nobody@example.com"))
    for table in ("topics", "entries", "posts"):
        assert "user_id" not in columns(old_db, table), table
