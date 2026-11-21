from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableView, QAbstractItemView, QMessageBox)
from qm_app.db import DatabaseError
from qm_app.repositories.sitzung_repo import SitzungRepository
from qm_app.ui.table_model import TableModel, Column
from qm_app.ui.sitzung_dialog import SitzungDialog


class SitzungView(QWidget):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.db, self.repo, self.loaded = database, SitzungRepository(database), False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Sitzungen'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Sitzungen suchen …')
        layout.addWidget(self.search)
        bar = QHBoxLayout()
        new, self.edit, refresh = QPushButton('Neue Sitzung'), QPushButton('Bearbeiten / Tagesordnung'), QPushButton('Aktualisieren')
        for button in (new, self.edit, refresh):
            bar.addWidget(button)
        bar.addStretch()
        layout.addLayout(bar)
        self.model = TableModel([Column('datum','Datum'), Column('bezeichnung','Bezeichnung'),
            Column('sitzungsart','Art'), Column('ort','Ort'), Column('status','Status')])
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(self.model.SortRole)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.message = QLabel()
        layout.addWidget(self.message)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        self.table.doubleClicked.connect(self.open_selected)
        new.clicked.connect(self.create)
        self.edit.clicked.connect(self.open_selected)
        refresh.clicked.connect(self.reload)
        self.selection_changed()

    def selection_changed(self, *args):
        self.edit.setEnabled(bool(self.table.selectionModel().selectedRows()))

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded:
            self.reload()

    def reload(self):
        try:
            rows = self.repo.list()
            self.model.set_rows(rows)
            self.table.resizeColumnsToContents()
            self.message.setText(f'{len(rows)} Sitzungen geladen')
            self.loaded = True
        except DatabaseError as error:
            self.message.setText(str(error))
        self.selection_changed()

    def create(self):
        SitzungDialog(self.db, parent=self).exec()
        self.reload()

    def open_selected(self, *args):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        source = self.proxy.mapToSource(indexes[0])
        try:
            s, participants = self.repo.get(self.model.rows[source.row()].id)
            SitzungDialog(self.db, s, participants, self).exec()
        except DatabaseError as error:
            QMessageBox.warning(self, 'Laden fehlgeschlagen', str(error))
        self.reload()
