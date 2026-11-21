from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import psycopg2
import pytest
from PySide6.QtCore import QSettings, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from qm_app.config import ConnectionProfile, Settings
from qm_app.db import ConcurrencyError, Database, DatabaseError
from qm_app.ui.login_dialog import LoginDialog
from qm_app.ui.main_window import MainWindow
from qm_app.ui.table_model import Column, TableModel


def settings_at(tmp_path):
    return Settings(QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat))


def test_login_and_navigation(app, tmp_path):
    settings = settings_at(tmp_path)
    db = MagicMock()
    db.user = 'qm_user'
    connect = MagicMock(return_value=db)
    dialog = LoginDialog(settings=settings, connect=connect)
    dialog.user.setText('qm_user')
    dialog.password.setText('private-secret')
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.database is db
    assert dialog.password.text() == ''
    assert settings.load_profile().user == 'qm_user'
    assert 'private-secret' not in (tmp_path / 'settings.ini').read_text()
    connect.assert_called_once_with(ConnectionProfile(user='qm_user'), 'private-secret')
    window = MainWindow(db)
    window.show()
    for index in range(4):
        window.navigation.setCurrentRow(index)
        assert window.pages.currentIndex() == index
    window.close()
    dialog.close()


def test_failed_login_does_not_save_profile(app, tmp_path, monkeypatch):
    settings = settings_at(tmp_path)
    monkeypatch.setattr(QMessageBox, 'warning', MagicMock())
    dialog = LoginDialog(settings=settings, connect=MagicMock(side_effect=DatabaseError('Fehler')))
    dialog.user.setText('failed_user')
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.database is None
    assert settings.load_profile().user == ''
    assert dialog.buttons.isEnabled()
    assert app.overrideCursor() is None
    dialog.close()


def test_password_and_invalid_port(app, tmp_path):
    settings = settings_at(tmp_path)
    settings.settings.setValue('connection/port', 'broken')
    assert settings.load_profile().port == 5432
    settings.settings.setValue('connection/password', 'old-secret')
    settings.save_profile(ConnectionProfile(user='tester'))
    assert not settings.settings.contains('connection/password')


def test_table_sort_and_filter(app):
    model = TableModel([Column('datum', 'Datum'), Column('titel', 'Titel')], [
        {'datum': date(2026, 2, 1), 'titel': 'Audit'},
        {'datum': date(2025, 12, 31), 'titel': 'Hygiene'},
    ])
    proxy = QSortFilterProxyModel()
    proxy.setSourceModel(model)
    proxy.setSortRole(model.SortRole)
    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    assert proxy.data(proxy.index(0, 0)) == '31.12.2025'
    proxy.setFilterKeyColumn(1)
    proxy.setFilterFixedString('Audit')
    assert proxy.rowCount() == 1
    model.set_rows([])
    assert proxy.rowCount() == 0


@pytest.mark.parametrize('failure', [None, ConcurrencyError(), ValueError('invalid'), psycopg2.OperationalError('secret server details')])
def test_transaction_context(failure):
    connection = MagicMock()
    database = Database(connection, 'tester')
    if failure is None:
        with database.transaction() as cursor:
            cursor.execute('SELECT 1')
        assert connection.__exit__.call_args.args == (None, None, None)
    else:
        expected = DatabaseError if isinstance(failure, psycopg2.Error) else type(failure)
        with pytest.raises(expected) as captured:
            with database.transaction():
                raise failure
        assert connection.__exit__.call_args.args[0] is type(failure)
        assert 'secret server details' not in str(captured.value)
