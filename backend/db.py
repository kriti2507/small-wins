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
