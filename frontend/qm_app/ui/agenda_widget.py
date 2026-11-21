from dataclasses import replace
from uuid import UUID
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QPlainTextEdit, QDialogButtonBox, QMessageBox,
    QTableView, QAbstractItemView, QPushButton, QTabWidget)
from qm_app.db import DatabaseError, ConcurrencyError
from qm_app.models import Besprechung, BESPRECHUNG_STATUS
from qm_app.repositories.besprechung_repo import BesprechungRepository
from qm_app.repositories.thema_repo import ThemaRepository
from qm_app.repositories.sitzung_repo import SitzungRepository
from qm_app.repositories.verlauf_repo import VerlaufRepository
from qm_app.ui.table_model import TableModel, Column
from qm_app.ui.verlauf_widget import VerlaufWidget


class AgendaDialog(QDialog):
    def __init__(self, database, sitzung_id, item=None, parent=None):
        super().__init__(parent)
        self.db, self.sitzung_id, self.item = database, sitzung_id, item
        self.repo = BesprechungRepository(database)
        self.setWindowTitle('Tagesordnungspunkt bearbeiten' if item else 'Thema zur Tagesordnung hinzufügen')
        self.resize(780, 650)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        page = QWidget()
        form = QFormLayout(page)
        self.thema = QComboBox()
        for t in ThemaRepository(database).list():
            self.thema.addItem(f'{t.titel} · {str(t.id)[:8]}', str(t.id))
        self.thema.setEnabled(item is None)
        self.top = QLineEdit()
        self.top.setMaxLength(50)
        self.order = QLineEdit()
        self.order.setValidator(QIntValidator(-2147483648, 2147483647, self))
        self.order.setPlaceholderText('Optional: numerische Sortierung')
        self.status = QComboBox()
        self.status.addItems(BESPRECHUNG_STATUS)
        self.result_text = QPlainTextEdit()
        self.decision = QPlainTextEdit()
        self.target = QComboBox()
        self.target.addItem('Keine Folgesitzung festgelegt', None)
        for s in SitzungRepository(database).list():
            if s.id != sitzung_id:
                self.target.addItem(f'{s.datum:%d.%m.%Y} – {s.bezeichnung} · {str(s.id)[:8]}', str(s.id))
        for label, field in [('Thema', self.thema), ('TOP-Nr.', self.top), ('Reihenfolge', self.order),
            ('Status', self.status), ('Ergebnis', self.result_text), ('Beschluss', self.decision), ('Vertagt nach', self.target)]:
            form.addRow(label, field)
        note = QLabel('Eine Vertagung verknüpft die Folgesitzung. Dort wird kein TOP automatisch angelegt.')
        note.setWordWrap(True)
        form.addRow(note)
        tabs.addTab(page, 'Tagesordnungspunkt')
        self.history = VerlaufWidget(VerlaufRepository(database), 'qm.besprechung', item.id if item else None)
        tabs.addTab(self.history, 'Verlauf')
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('TOP speichern')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Abbrechen')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.populate()

    def populate(self):
        item = self.item
        if item:
            self.thema.setCurrentIndex(self.thema.findData(str(item.thema_id)))
            self.top.setText(item.top_nr or '')
            self.order.setText(str(item.reihenfolge) if item.reihenfolge is not None else '')
            self.status.setCurrentText(item.status)
            self.result_text.setPlainText(item.ergebnis or '')
            self.decision.setPlainText(item.beschluss or '')
            self.target.setCurrentIndex(max(0, self.target.findData(str(item.vertagung_nach_sitzung_id) if item.vertagung_nach_sitzung_id else None)))

    def accept(self):
        if self.order.text() and not self.order.hasAcceptableInput():
            QMessageBox.warning(self, 'Reihenfolge', 'Bitte eine gültige ganze Zahl eingeben.')
            return
        values = dict(thema_id=UUID(self.thema.currentData()) if self.thema.currentData() else None, top_nr=self.top.text().strip() or None,
            reihenfolge=int(self.order.text()) if self.order.text() else None,
            status=self.status.currentText(), ergebnis=self.result_text.toPlainText().strip() or None,
            beschluss=self.decision.toPlainText().strip() or None,
            vertagung_nach_sitzung_id=UUID(self.target.currentData()) if self.target.currentData() else None)
        try:
            if self.item:
                self.repo.update(replace(self.item, **values))
            else:
                self.repo.create(Besprechung(sitzung_id=self.sitzung_id, erstellt_von=self.db.user, **values))
        except ConcurrencyError:
            QMessageBox.warning(self, 'Zwischenzeitliche Änderung',
                'Der aktuelle TOP wird neu geladen. Ungespeicherte Eingaben werden ersetzt; bitte erneut prüfen.')
            try:
                self.item = self.repo.get(self.item.id)
                self.populate()
                self.history.reload()
            except DatabaseError as error:
                QMessageBox.warning(self, 'Laden fehlgeschlagen', str(error))
                self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
            return
        except DatabaseError as error:
            QMessageBox.warning(self, 'Speichern nicht möglich', str(error))
            return
        super().accept()


class AgendaWidget(QWidget):
    def __init__(self, database, sitzung_id, parent=None):
        super().__init__(parent)
        self.db, self.sitzung_id = database, sitzung_id
        self.repo = BesprechungRepository(database)
        layout = QVBoxLayout(self)
        self.message = QLabel('TOPs werden unabhängig von den Sitzungsstammdaten gespeichert.')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        bar = QHBoxLayout()
        self.add = QPushButton('Thema zuordnen')
        self.edit = QPushButton('TOP bearbeiten')
        refresh = QPushButton('Aktualisieren')
        for button in (self.add, self.edit, refresh):
            bar.addWidget(button)
        layout.addLayout(bar)
        self.model = TableModel([Column('reihenfolge', 'Reihenfolge'), Column('top_nr', 'TOP'),
            Column('thema_titel', 'Thema'), Column('status', 'Status'), Column('beschluss', 'Beschluss')])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.add.clicked.connect(self.create)
        self.edit.clicked.connect(self.open_selected)
        refresh.clicked.connect(self.reload)
        self.table.doubleClicked.connect(self.open_selected)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        if sitzung_id is None:
            self.message.setText('Bitte die neue Sitzung zuerst speichern und erneut öffnen, um TOPs zuzuordnen.')
            self.add.setEnabled(False)
            refresh.setEnabled(False)
        self.reload()

    def selection_changed(self, *args):
        self.edit.setEnabled(bool(self.table.selectionModel().selectedRows()))

    def reload(self):
        try:
            self.model.set_rows(self.repo.list(self.sitzung_id) if self.sitzung_id else [])
            self.table.resizeColumnsToContents()
        except DatabaseError as error:
            self.message.setText(str(error))
        self.selection_changed()

    def create(self):
        try:
            AgendaDialog(self.db, self.sitzung_id, parent=self).exec()
        except DatabaseError as error:
            QMessageBox.warning(self, 'Laden fehlgeschlagen', str(error))
        self.reload()

    def open_selected(self, *args):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        try:
            item = self.repo.get(self.model.rows[indexes[0].row()]['id'])
            AgendaDialog(self.db, self.sitzung_id, item, self).exec()
        except DatabaseError as error:
            QMessageBox.warning(self, 'Laden fehlgeschlagen', str(error))
        self.reload()
