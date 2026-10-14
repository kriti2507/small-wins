import os

import psycopg
import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def make_user(sub, email):
    """Insert (or refresh) a users row and return its id."""
    import app
    import db
    with app.app.app_context():
        return db.upsert_user(sub, email, None, None)["id"]


@pytest.fixture(scope="session")
def _schema():
    if not TEST_DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to run database-backed tests")
    with open(SCHEMA_PATH) as f:
        ddl = f.read()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute("drop table if exists posts, entries, topics, users cascade")
        conn.execute(ddl)
    return TEST_DATABASE_URL


@pytest.fixture()
def test_db(_schema, monkeypatch):
    """Point db.py at the test database and start each test with empty tables."""
    import db
    monkeypatch.setattr(db, "DATABASE_URL", _schema)
    with psycopg.connect(_schema, autocommit=True) as conn:
        conn.execute("truncate topics, entries, posts, users cascade")
    return _schema


@pytest.fixture()
def app_ctx(test_db):
    """An app context so db.get_conn caches on `g` and is closed on teardown."""
    import app
    with app.app.app_context():
        yield


@pytest.fixture()
def anon_client(monkeypatch):
    """No session and no database: for requests that end before any query.

    Clears auth settings that backend/.env may have loaded, so the local
    config can't change test results.
    """
    import app
    for name in ("MCP_SERVICE_TOKEN", "ALLOWED_EMAILS"):
        monkeypatch.delenv(name, raising=False)
    app.app.config["TESTING"] = True
    return app.app.test_client()


@pytest.fixture()
def no_db_client(anon_client):
    """Signed in, for endpoints that never touch the database."""
    with anon_client.session_transaction() as s:
        s["user_id"] = 1
    return anon_client


@pytest.fixture()
def db_anon_client(test_db, anon_client):
    """Signed out, with an empty test database."""
    return anon_client


@pytest.fixture()
def client(test_db, anon_client):
    """Signed in as a real users row, with an empty test database."""
    import app
    import db
    with app.app.app_context():
        user = db.upsert_user("sub-test", "test@example.com", "Test", None)
    with anon_client.session_transaction() as s:
        s["user_id"] = user["id"]
    return anon_client


@pytest.fixture()
def second_client(test_db, anon_client):
    """A different signed-in user, with its own cookie jar."""
    import app
    uid = make_user("sub-second", "second@example.com")
    c = app.app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
    return c
