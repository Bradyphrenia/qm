from datetime import date
from PySide6.QtCore import Qt,QSortFilterProxyModel
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QTableView,QAbstractItemView,QMessageBox
from qm_app.db import DatabaseError
from qm_app.models import MASSNAHME_STATUS
from qm_app.repositories.massnahme_repo import MassnahmeRepository
from qm_app.ui.massnahme_dialog import MassnahmeDialog
from qm_app.ui.table_model import TableModel,Column


def overdue(item):
    return bool(item.faellig_am and item.faellig_am < date.today() and item.abgeschlossen_am is None
        and item.status in ('offen','in_bearbeitung','zurueckgestellt'))


class MassnahmeModel(TableModel):
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and 0 <= index.row() < len(self.rows) and overdue(self.rows[index.row()]):
            if role==Qt.ItemDataRole.BackgroundRole:
                return QColor('#fff0d9')
            if role==Qt.ItemDataRole.ForegroundRole:
                return QColor('#7a3300')
            if role==Qt.ItemDataRole.ToolTipRole:
                return 'Überfällige Maßnahme'
        return super().data(index,role)


class MassnahmeFilter(QSortFilterProxyModel):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.status,self.owner='',''

    def set_filters(self,status,owner):
        self.status,self.owner=status,owner.strip().casefold()
        self.invalidate()

    def filterAcceptsRow(self,row,parent):
        item=self.sourceModel().rows[row]
        return (not self.status or item.status==self.status) and self.owner in item.verantwortlich.casefold()


class MassnahmeView(QWidget):
    def __init__(self,database,thema_id=None,parent=None,scoped=False):
        super().__init__(parent)
        self.db,self.thema_id,self.scoped=database,thema_id,scoped
        self.repo=MassnahmeRepository(database)
        self.loaded=False
        layout=QVBoxLayout(self)
        note=QLabel('Maßnahmen werden separat gespeichert. Orange markiert: überfällige Umsetzung.')
        note.setWordWrap(True)
        layout.addWidget(note)
        bar=QHBoxLayout()
        self.status=QComboBox()
        self.status.addItem('Alle Status','')
        for status in MASSNAHME_STATUS:
            self.status.addItem(status,status)
        self.owner=QLineEdit()
        self.owner.setPlaceholderText('Verantwortliche filtern …')
        bar.addWidget(self.status)
        bar.addWidget(self.owner)
        layout.addLayout(bar)
        bar=QHBoxLayout()
        self.new,self.edit,self.refresh=QPushButton('Neue Maßnahme'),QPushButton('Bearbeiten'),QPushButton('Aktualisieren')
        for button in (self.new,self.edit,self.refresh):
            bar.addWidget(button)
        layout.addLayout(bar)
        self.model=MassnahmeModel([Column('titel','Titel'),Column('verantwortlich','Verantwortlich'),Column('status','Status'),Column('faellig_am','Fällig am')])
        self.proxy=MassnahmeFilter(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(self.model.SortRole)
        self.table=QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(3,Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.message=QLabel()
        layout.addWidget(self.message)
        self.new.clicked.connect(self.create)
        self.edit.clicked.connect(self.open_selected)
        self.refresh.clicked.connect(self.reload)
        self.table.doubleClicked.connect(self.open_selected)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        self.status.currentIndexChanged.connect(self.filter)
        self.owner.textChanged.connect(self.filter)
        if scoped and thema_id is None:
            note.setText('Bitte das Thema zuerst speichern und erneut öffnen, um Maßnahmen anzulegen.')
            self.new.setEnabled(False)
        self.selection_changed()

    def showEvent(self,event):
        super().showEvent(event)
        if not self.loaded:
            self.reload()

    def filter(self,*args):
        self.proxy.set_filters(self.status.currentData() or '',self.owner.text())
        self.selection_changed()

    def selection_changed(self,*args):
        self.edit.setEnabled(bool(self.table.selectionModel().selectedRows()))

    def reload(self):
        try:
            rows=[] if self.scoped and self.thema_id is None else self.repo.list(self.thema_id)
            self.model.set_rows(rows)
            self.table.resizeColumnsToContents()
            self.message.setText(f'{len(rows)} Maßnahmen')
            self.loaded=True
        except DatabaseError as error:
            self.message.setText(str(error))
        self.selection_changed()

    def create(self):
        try:
            MassnahmeDialog(self.db,thema_id=self.thema_id,parent=self).exec()
        except DatabaseError as error:
            QMessageBox.warning(self,'Laden fehlgeschlagen',str(error))
        self.reload()

    def open_selected(self,*args):
        indexes=self.table.selectionModel().selectedRows()
        if not indexes:
            return
        try:
            item=self.repo.get(self.model.rows[self.proxy.mapToSource(indexes[0]).row()].id)
            MassnahmeDialog(self.db,item=item,parent=self).exec()
        except DatabaseError as error:
            QMessageBox.warning(self,'Laden fehlgeschlagen',str(error))
        self.reload()
