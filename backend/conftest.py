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


def make_grant(user_id, redeemed=True):
    """Create an MCP grant for user_id; return (grant_id, credential)."""
    import app
    import db
    import grants
    with app.app.app_context():
        credential = grants.mint(user_id, "Claude", "claude.ai")
        grant_id = int(credential.removeprefix("swg_").split(".")[0])
        if redeemed:
            db.redeem_grant(grant_id)
    return grant_id, credential


@pytest.fixture(scope="session")
def _schema():
    if not TEST_DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to run database-backed tests")
    # The next lines drop every table. Never let that reach a real Supabase
    # project; tests belong on a throwaway local Postgres.
    if "supabase" in TEST_DATABASE_URL.lower():
        pytest.exit("TEST_DATABASE_URL points at Supabase; refusing to wipe it", returncode=2)
    with open(SCHEMA_PATH) as f:
        ddl = f.read()
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        conn.execute("drop table if exists mcp_grants, posts, entries, topics, users cascade")
        conn.execute(ddl)
    return TEST_DATABASE_URL


@pytest.fixture()
def test_db(_schema, monkeypatch):
    """Point db.py at the test database and start each test with empty tables."""
    import db
    monkeypatch.setattr(db, "DATABASE_URL", _schema)
    with psycopg.connect(_schema, autocommit=True) as conn:
        conn.execute("truncate topics, entries, posts, mcp_grants, users cascade")
    return _schema


@pytest.fixture()
def app_ctx(test_db):
    """An app context so db.get_conn caches on `g` and is closed on teardown."""
    import app
    with app.app.app_context():
        yield


@pytest.fixture()
def anon_client():
    """No session and no database: for requests that end before any query."""
    import app
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
