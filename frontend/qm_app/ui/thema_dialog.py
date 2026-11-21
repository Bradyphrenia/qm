from dataclasses import replace
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QWidget, QTabWidget,
    QLineEdit, QPlainTextEdit, QComboBox, QDialogButtonBox, QMessageBox, QLabel)
from qm_app.db import DatabaseError, ConcurrencyError
from qm_app.models import Thema, THEMA_STATUS
from qm_app.ui.verlauf_widget import VerlaufWidget
from qm_app.ui.massnahme_view import MassnahmeView
from qm_app.ui.dokument_widget import DokumentWidget


class ThemaDialog(QDialog):
    def __init__(self, repository, history, thema=None, parent=None):
        super().__init__(parent)
        self.repo, self.history, self.thema = repository, history, thema
        self.saved_id = None
        self.setWindowTitle('Thema bearbeiten' if thema else 'Thema anlegen')
        self.resize(780, 620)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        form_page = QWidget()
        form = QFormLayout(form_page)
        self.titel = QLineEdit()
        self.titel.setMaxLength(255)
        self.kategorie = QLineEdit()
        self.kategorie.setMaxLength(100)
        self.prioritaet = QComboBox()
        self.prioritaet.setEditable(True)
        self.prioritaet.addItems(['', 'niedrig', 'mittel', 'hoch', 'kritisch'])
        self.prioritaet.lineEdit().setMaxLength(50)
        self.status = QComboBox()
        self.beschreibung = QPlainTextEdit()
        self.verantwortlich = QLineEdit()
        self.epz_fall_id = QLineEdit()
        self.epz_fall_id.setMaxLength(100)
        for label, field in [('Titel *', self.titel), ('Kategorie *', self.kategorie),
            ('Priorität', self.prioritaet), ('Status', self.status), ('Verantwortlich', self.verantwortlich),
            ('EPZ-Fall-ID', self.epz_fall_id), ('Beschreibung', self.beschreibung)]:
            form.addRow(label, field)
        self.version_label = QLabel()
        form.addRow(self.version_label)
        self.tabs.addTab(form_page, 'Stammdaten')
        self.verlauf = VerlaufWidget(history, 'qm.thema', thema.id if thema else None)
        self.tabs.addTab(self.verlauf, 'Verlauf')
        self.tabs.addTab(MassnahmeView(repository.db,thema.id if thema else None,scoped=True),'Maßnahmen')
        self.tabs.addTab(DokumentWidget(repository.db,'thema',thema.id if thema else None),'Dokumente')
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Speichern')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Abbrechen')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.populate()

    def populate(self):
        t = self.thema
        self.status.clear()
        statuses = [s for s in THEMA_STATUS if s != 'wiederaufgenommen' or (t and t.status == s)]
        if t and t.status in ('abgeschlossen', 'abgebrochen'):
            statuses = ['abgeschlossen', 'abgebrochen']
        self.status.addItems(statuses)
        self.titel.setText(t.titel if t else '')
        self.kategorie.setText(t.kategorie if t else '')
        self.prioritaet.setCurrentText((t.prioritaet or '') if t else '')
        self.status.setCurrentText(t.status if t else 'offen')
        self.verantwortlich.setText((t.verantwortlich or '') if t else '')
        self.epz_fall_id.setText((t.epz_fall_id or '') if t else '')
        self.beschreibung.setPlainText((t.beschreibung or '') if t else '')
        self.version_label.setText(f'Version {t.version}' if t else '* Pflichtfeld')

    def accept(self):
        values = dict(titel=self.titel.text().strip(), kategorie=self.kategorie.text().strip(),
            prioritaet=self.prioritaet.currentText().strip() or None, status=self.status.currentText(),
            verantwortlich=self.verantwortlich.text().strip() or None,
            epz_fall_id=self.epz_fall_id.text().strip() or None,
            beschreibung=self.beschreibung.toPlainText().strip() or None)
        try:
            if self.thema:
                self.repo.update(replace(self.thema, **values))
                self.saved_id = self.thema.id
            else:
                self.saved_id = self.repo.create(Thema(erstellt_von=self.repo.db.user, **values))
        except ConcurrencyError:
            QMessageBox.warning(self, 'Zwischenzeitliche Änderung',
                'Das Thema wurde zwischenzeitlich geändert. Der aktuelle Stand wird geladen; '
                'deine nicht gespeicherten Eingaben werden ersetzt. Bitte erneut prüfen.')
            try:
                self.thema = self.repo.get(self.thema.id)
                self.populate()
                self.verlauf.reload()
            except DatabaseError as error:
                QMessageBox.warning(self, 'Neuladen fehlgeschlagen', str(error))
                self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
            return
        except DatabaseError as error:
            QMessageBox.warning(self, 'Speichern nicht möglich', str(error))
            return
        super().accept()


class ReopenDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Thema wiederaufnehmen')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Bitte die Wiederaufnahme begründen:'))
        self.reason = QPlainTextEdit()
        layout.addWidget(self.reason)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Wiederaufnehmen')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Abbrechen')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        if not self.reason.toPlainText().strip():
            QMessageBox.warning(self, 'Begründung fehlt', 'Bitte eine Begründung eingeben.')
            return
        super().accept()
