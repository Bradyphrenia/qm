from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from PySide6.QtWidgets import QMessageBox, QDialog
from qm_app.db import ConcurrencyError, DatabaseError
from qm_app.models import Thema
from qm_app.ui.table_model import TableModel, Column
from qm_app.ui.thema_view import ThemaFilter, ThemaView
from qm_app.ui.thema_dialog import ThemaDialog, ReopenDialog


def thema(**kwargs):
    return Thema(titel='Prüfung Dokumente', kategorie='Audit', erstellt_von='tester', **kwargs)


def test_combined_filters(app):
    model = TableModel([Column('titel', 'Titel')], [thema(status='offen'),
        Thema(titel='Hygiene', kategorie='Prozess', status='abgeschlossen', erstellt_von='tester')])
    proxy = ThemaFilter()
    proxy.setSourceModel(model)
    proxy.set_filters('offen', 'Audit', 'PRÜFUNG')
    assert proxy.rowCount() == 1
    proxy.set_filters('abgeschlossen', 'Audit')
    assert proxy.rowCount() == 0
    proxy.set_filters(text='hygiene')
    assert proxy.rowCount() == 1


def test_dialog_conflict_reloads(app, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', MagicMock())
    repo, history = MagicMock(), MagicMock()
    history.list.return_value = []
    original = thema(id=uuid4(), version=1)
    updated = replace(original, titel='Zwischenzeitlich geändert', version=2)
    repo.update.side_effect = ConcurrencyError()
    repo.get.return_value = updated
    dialog = ThemaDialog(repo, history, original)
    dialog.titel.setText('Meine Änderung')
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.titel.text() == updated.titel
    assert dialog.thema.version == 2
    assert dialog.verlauf.details.isReadOnly()
    dialog.close()


def test_reopen_requires_reason(app, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', MagicMock())
    dialog = ReopenDialog()
    dialog.reason.setPlainText('   ')
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    dialog.reason.setPlainText('Neue Erkenntnisse')
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_view_selection_uses_filtered_source(app):
    database = MagicMock()
    view = ThemaView(database)
    first = thema(id=uuid4())
    second = replace(first, id=uuid4(), titel='Zielthema')
    view.repo = MagicMock()
    view.repo.list.return_value = [first, second]
    view.reload()
    view.search.setText('Zielthema')
    view.table.selectRow(0)
    assert view.selected().id == second.id
    assert view.edit.isEnabled()
    view.close()
