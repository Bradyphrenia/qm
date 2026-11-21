"""Read-only connection check. Use a dedicated test database, never production."""
import os
import psycopg2
from psycopg2.extras import register_uuid
import pytest
from qm_app.db import Database


def test_database_transaction_against_postgres():
    dsn = os.environ.get('QM_TEST_DSN')
    if not dsn:
        pytest.skip('QM_TEST_DSN ist nicht gesetzt')
    connection = psycopg2.connect(dsn, connect_timeout=5)
    register_uuid(conn_or_curs=connection)
    database = Database(connection, 'test')
    try:
        with database.transaction() as cursor:
            cursor.execute("SELECT to_regclass('qm.thema') AS thema, current_user AS benutzer")
            row = cursor.fetchone()
            assert row['thema'] is not None
            assert row['benutzer']
    finally:
        database.close()
