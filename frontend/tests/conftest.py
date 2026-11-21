import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope='session')
def app():
    application = QApplication.instance() or QApplication([])
    yield application


from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid
from qm_app.db import translate_error


@pytest.fixture
def database():
    dsn = os.environ.get('QM_TEST_DSN')
    if not dsn:
        pytest.skip('QM_TEST_DSN ist nicht gesetzt')
    connection = psycopg2.connect(dsn, connect_timeout=5)
    register_uuid(conn_or_curs=connection)
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_user')
        username = cursor.fetchone()[0]

    class RollbackDatabase:
        user = username

        @contextmanager
        def transaction(self):
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SAVEPOINT repository_test')
                try:
                    yield cursor
                except BaseException as error:
                    cursor.execute('ROLLBACK TO SAVEPOINT repository_test')
                    if isinstance(error, psycopg2.Error):
                        raise translate_error(error) from None
                    raise
                finally:
                    cursor.execute('RELEASE SAVEPOINT repository_test')
    try:
        yield RollbackDatabase()
    finally:
        connection.rollback()
        connection.close()

