from dataclasses import replace
from datetime import date
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QLineEdit, QComboBox, QDateEdit, QTimeEdit, QCheckBox, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton, QDialogButtonBox, QMessageBox)
from qm_app.db import DatabaseError, ConcurrencyError
from qm_app.models import Sitzung, SitzungTeilnehmer, SITZUNG_STATUS
from qm_app.repositories.sitzung_repo import SitzungRepository
from qm_app.repositories.verlauf_repo import VerlaufRepository
from qm_app.ui.verlauf_widget import VerlaufWidget
from qm_app.ui.agenda_widget import AgendaWidget
from qm_app.ui.dokument_widget import DokumentWidget


class SitzungDialog(QDialog):
    def __init__(self, database, sitzung=None, participants=(), parent=None):
        super().__init__(parent)
        self.db, self.sitzung = database, sitzung
        self.repo = SitzungRepository(database)
        self.setWindowTitle('Sitzung bearbeiten' if sitzung else 'Sitzung anlegen')
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        page = QWidget()
        form = QFormLayout(page)
        self.fields = {}
        for name, title, limit in [('bezeichnung','Bezeichnung *',255), ('sitzungsart','Sitzungsart',100),
            ('ort','Ort',255), ('leitung','Leitung',100), ('protokollfuehrung','Protokollführung',100)]:
            field = QLineEdit()
            field.setMaxLength(limit)
            self.fields[name] = field
            form.addRow(title, field)
        self.datum = QDateEdit()
        self.datum.setCalendarPopup(True)
        self.datum.setDisplayFormat('dd.MM.yyyy')
        form.addRow('Datum', self.datum)
        self.times = {}
        for name, title in [('beginn','Beginn'), ('ende','Ende')]:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0,0,0,0)
            check, edit = QCheckBox('Angeben'), QTimeEdit()
            edit.setDisplayFormat('HH:mm:ss')
            check.toggled.connect(edit.setEnabled)
            row_layout.addWidget(check)
            row_layout.addWidget(edit)
            self.times[name] = (check, edit)
            form.addRow(title, row)
        self.status = QComboBox()
        self.status.addItems(SITZUNG_STATUS)
        form.addRow('Status', self.status)
        self.tabs.addTab(page, 'Stammdaten')
        participant_page = QWidget()
        participant_layout = QVBoxLayout(participant_page)
        participant_layout.addWidget(QLabel('Teilnehmende werden mit „Sitzung speichern“ übernommen.'))
        self.participants = QTableWidget(0, 6)
        self.participants.setHorizontalHeaderLabels(['Person *','Rolle','Anwesend','Vertretung','Bemerkung','ID'])
        self.participants.setColumnHidden(5, True)
        for column, width in enumerate((220, 130, 90, 160, 220)):
            self.participants.setColumnWidth(column, width)
        self.participants.horizontalHeader().setStretchLastSection(True)
        participant_layout.addWidget(self.participants)
        bar = QHBoxLayout()
        add, remove = QPushButton('Person hinzufügen'), QPushButton('Ausgewählte Person entfernen')
        bar.addWidget(add)
        bar.addWidget(remove)
        add.clicked.connect(lambda: self.add_person())
        remove.clicked.connect(self.remove_person)
        participant_layout.addLayout(bar)
        self.tabs.addTab(participant_page, 'Teilnehmende')
        self.agenda = AgendaWidget(database, sitzung.id if sitzung else None)
        self.tabs.addTab(self.agenda, 'Tagesordnung')
        self.history = VerlaufWidget(VerlaufRepository(database), 'qm.sitzung', sitzung.id if sitzung else None)
        self.tabs.addTab(self.history, 'Verlauf')
        self.tabs.addTab(DokumentWidget(database,'sitzung',sitzung.id if sitzung else None),'Dokumente')
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Sitzung speichern')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Schließen ohne Stammdaten zu speichern')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.populate(participants)

    def populate(self, participants):
        s = self.sitzung
        for name, field in self.fields.items():
            field.setText((getattr(s, name) or '') if s else '')
        d = s.datum if s else date.today()
        self.datum.setDate(QDate(d.year, d.month, d.day))
        for name, (check, edit) in self.times.items():
            value = getattr(s, name) if s else None
            check.setChecked(value is not None)
            edit.setEnabled(value is not None)
            edit.setTime(QTime(value.hour, value.minute, value.second) if value else QTime(9,0))
        self.status.setCurrentText(s.status if s else 'geplant')
        self.participants.setRowCount(0)
        for p in participants:
            self.add_person(p)

    def add_person(self, p=None):
        row = self.participants.rowCount()
        self.participants.insertRow(row)
        values = [p.person if p else '', p.rolle if p else '', '', p.vertretung_durch if p else '', p.bemerkung if p else '', '']
        for col, value in enumerate(values):
            self.participants.setItem(row, col, QTableWidgetItem(value or ''))
        self.participants.item(row, 5).setData(Qt.ItemDataRole.UserRole, p.id if p else None)
        check = self.participants.item(row, 2)
        check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        check.setCheckState(Qt.CheckState.Checked if p is None or p.anwesend else Qt.CheckState.Unchecked)

    def remove_person(self):
        row = self.participants.currentRow()
        if row >= 0:
            self.participants.removeRow(row)

    def collect_participants(self):
        result = []
        for row in range(self.participants.rowCount()):
            def text(col):
                return self.participants.item(row, col).text().strip() or None
            result.append(SitzungTeilnehmer(id=self.participants.item(row,5).data(Qt.ItemDataRole.UserRole),
                sitzung_id=self.sitzung.id if self.sitzung else None,
                person=text(0) or '', rolle=text(1), anwesend=self.participants.item(row,2).checkState()==Qt.CheckState.Checked,
                vertretung_durch=text(3), bemerkung=text(4)))
        return result

    def accept(self):
        values = {name: field.text().strip() or None for name, field in self.fields.items()}
        values['bezeichnung'] = values['bezeichnung'] or ''
        values.update(datum=self.datum.date().toPython(), status=self.status.currentText())
        for name, (check, edit) in self.times.items():
            values[name] = edit.time().toPython() if check.isChecked() else None
        try:
            participants = self.collect_participants()
            if self.sitzung:
                self.repo.update(replace(self.sitzung, **values), participants)
            else:
                self.repo.create(Sitzung(erstellt_von=self.db.user, **values), participants)
        except ConcurrencyError:
            QMessageBox.warning(self, 'Zwischenzeitliche Änderung',
                'Sitzung und Teilnehmende werden neu geladen. Ungespeicherte Eingaben werden ersetzt; bitte erneut prüfen.')
            try:
                self.sitzung, participants = self.repo.get(self.sitzung.id)
                self.populate(participants)
                self.history.reload()
                self.agenda.reload()
            except DatabaseError as error:
                QMessageBox.warning(self, 'Laden fehlgeschlagen', str(error))
                self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
            return
        except DatabaseError as error:
            QMessageBox.warning(self, 'Speichern nicht möglich', str(error))
            return
        super().accept()
