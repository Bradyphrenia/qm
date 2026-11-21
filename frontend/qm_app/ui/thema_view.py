from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QPushButton, QTableView, QAbstractItemView, QLabel, QMessageBox, QDialog)
from qm_app.db import DatabaseError
from qm_app.models import THEMA_STATUS
from qm_app.repositories.thema_repo import ThemaRepository
from qm_app.repositories.verlauf_repo import VerlaufRepository
from qm_app.ui.table_model import TableModel, Column
from qm_app.ui.thema_dialog import ThemaDialog, ReopenDialog


class ThemaFilter(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status, self.kategorie, self.text = '', '', ''

    def set_filters(self, status='', kategorie='', text=''):
        self.status, self.kategorie, self.text = status, kategorie, text.casefold().strip()
        self.invalidate()

    def filterAcceptsRow(self, row, parent):
        thema = self.sourceModel().rows[row]
        text = ' '.join(str(value or '') for value in
            (thema.titel, thema.beschreibung, thema.kategorie, thema.verantwortlich, thema.epz_fall_id)).casefold()
        return (not self.status or thema.status == self.status) and (
            not self.kategorie or thema.kategorie == self.kategorie) and (not self.text or self.text in text)


class ThemaView(QWidget):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.repo = ThemaRepository(database)
        self.history = VerlaufRepository(database)
        self.loaded = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Themen'))
        filters = QHBoxLayout()
        self.status = QComboBox()
        self.status.addItem('Alle Status', '')
        for status in THEMA_STATUS:
            self.status.addItem(status, status)
        self.category = QComboBox()
        self.category.addItem('Alle Kategorien', '')
        self.search = QLineEdit()
        self.search.setPlaceholderText('Titel, Beschreibung, Verantwortliche oder Fall-ID suchen …')
        for widget in (self.status, self.category, self.search):
            filters.addWidget(widget)
        layout.addLayout(filters)
        actions = QHBoxLayout()
        self.new = QPushButton('Neues Thema')
        self.edit = QPushButton('Bearbeiten / Verlauf')
        self.reopen = QPushButton('Wiederaufnehmen')
        self.refresh = QPushButton('Aktualisieren')
        for button in (self.new, self.edit, self.reopen, self.refresh):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.model = TableModel([Column('titel', 'Titel'), Column('kategorie', 'Kategorie'),
            Column('status', 'Status'), Column('prioritaet', 'Priorität'),
            Column('verantwortlich', 'Verantwortlich'), Column('erfasst_am', 'Erfasst am')])
        self.proxy = ThemaFilter(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(self.model.SortRole)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(5, Qt.SortOrder.DescendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.new.clicked.connect(self.create)
        self.edit.clicked.connect(self.open_selected)
        self.reopen.clicked.connect(self.reopen_selected)
        self.refresh.clicked.connect(self.reload)
        self.table.doubleClicked.connect(self.open_selected)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        self.status.currentIndexChanged.connect(self.apply_filters)
        self.category.currentIndexChanged.connect(self.apply_filters)
        self.search.textChanged.connect(self.apply_filters)
        self.selection_changed()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded:
            self.reload()

    def selected(self):
        indexes = self.table.selectionModel().selectedRows()
        return self.model.rows[self.proxy.mapToSource(indexes[0]).row()] if indexes else None

    def selection_changed(self, *args):
        selected = self.selected()
        self.edit.setEnabled(selected is not None)
        self.reopen.setEnabled(selected is not None and selected.status != 'wiederaufgenommen')

    def apply_filters(self, *args):
        self.proxy.set_filters(self.status.currentData() or '', self.category.currentData() or '', self.search.text())
        self.selection_changed()

    def reload(self):
        try:
            rows = self.repo.list()
        except DatabaseError as error:
            self.message.setText('Laden fehlgeschlagen: ' + str(error))
            return
        selected = self.selected()
        category = self.category.currentData()
        self.model.set_rows(rows)
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem('Alle Kategorien', '')
        for value in sorted({row.kategorie for row in rows}, key=str.casefold):
            self.category.addItem(value, value)
        index = self.category.findData(category)
        self.category.setCurrentIndex(max(index, 0))
        self.category.blockSignals(False)
        self.apply_filters()
        if selected:
            for row in range(self.proxy.rowCount()):
                source = self.proxy.mapToSource(self.proxy.index(row, 0))
                if self.model.rows[source.row()].id == selected.id:
                    self.table.selectRow(row)
                    break
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.message.setText(f'{len(rows)} Themen geladen')
        self.loaded = True
        self.selection_changed()

    def create(self):
        if ThemaDialog(self.repo, self.history, parent=self).exec() == QDialog.DialogCode.Accepted:
            self.reload()

    def open_selected(self, *args):
        selected = self.selected()
        if selected is None:
            return
        try:
            current = self.repo.get(selected.id)
        except DatabaseError as error:
            QMessageBox.warning(self, 'Thema nicht verfügbar', str(error))
            self.reload()
            return
        ThemaDialog(self.repo, self.history, current, self).exec()
        self.reload()

    def reopen_selected(self):
        selected = self.selected()
        if selected is None:
            return
        dialog = ReopenDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repo.reopen(selected.id, selected.version, dialog.reason.toPlainText())
        except DatabaseError as error:
            QMessageBox.warning(self, 'Wiederaufnahme nicht möglich', str(error))
        self.reload()
