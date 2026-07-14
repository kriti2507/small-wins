import os

import psycopg
import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


@pytest.fixture(scope="session")
def _schema():
    if not TEST_DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to run database-backed tests")
    with open(SCHEMA_PATH) as f:
        ddl = f.read()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute("drop table if exists posts, entries, topics cascade")
        conn.execute(ddl)
    return TEST_DATABASE_URL


@pytest.fixture()
def test_db(_schema, monkeypatch):
    """Point db.py at the test database and start each test with empty tables."""
    import db
    monkeypatch.setattr(db, "DATABASE_URL", _schema)
    with psycopg.connect(_schema, autocommit=True) as conn:
        conn.execute("truncate topics, entries, posts cascade")
    return _schema


@pytest.fixture()
def app_ctx(test_db):
    """An app context so db.get_conn caches on `g` and is closed on teardown."""
    import app
    with app.app.app_context():
        yield
