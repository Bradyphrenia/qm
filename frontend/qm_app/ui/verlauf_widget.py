import json
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QPlainTextEdit, QLabel, QAbstractItemView
from qm_app.db import DatabaseError
from qm_app.ui.table_model import TableModel, Column


class VerlaufWidget(QWidget):
    def __init__(self, repository, entitaet, id, parent=None):
        super().__init__(parent)
        self.repository, self.entitaet, self.id = repository, entitaet, id
        layout = QVBoxLayout(self)
        self.message = QLabel()
        layout.addWidget(self.message)
        self.model = TableModel([Column('zeitpunkt', 'Zeitpunkt'), Column('benutzer', 'Benutzer'), Column('ereignis_art', 'Ereignis')])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.table)
        layout.addWidget(self.details)
        self.table.selectionModel().currentRowChanged.connect(self.show_details)
        self.reload()

    def reload(self):
        self.details.clear()
        if self.id is None:
            self.message.setText('Der Verlauf steht nach dem ersten Speichern zur Verfügung.')
            return
        try:
            rows = self.repository.list(self.entitaet, self.id)
            self.model.set_rows(rows)
            self.message.setText(f'{len(rows)} Verlaufseinträge')
            self.table.resizeColumnsToContents()
            if rows:
                self.table.selectRow(0)
        except DatabaseError as error:
            self.model.set_rows([])
            self.message.setText(str(error))

    def show_details(self, index, previous=None):
        if not index.isValid():
            self.details.clear()
            return
        item = self.model.rows[index.row()]
        self.details.setPlainText(json.dumps({'Begründung': item.begruendung,
            'Vorher': item.alte_werte, 'Nachher': item.neue_werte}, ensure_ascii=False, indent=2, default=str))
