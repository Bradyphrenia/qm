from dataclasses import replace
from datetime import date
from uuid import UUID
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QHBoxLayout,QWidget,
    QTabWidget,QSizePolicy,QLineEdit,QPlainTextEdit,QComboBox,QCheckBox,QDateEdit,QDialogButtonBox,QMessageBox,QLabel)
from qm_app.db import DatabaseError,ConcurrencyError
from qm_app.models import Massnahme,MASSNAHME_STATUS,WIRKSAMKEIT_ERGEBNIS
from qm_app.repositories.massnahme_repo import MassnahmeRepository
from qm_app.repositories.thema_repo import ThemaRepository
from qm_app.repositories.verlauf_repo import VerlaufRepository
from qm_app.ui.verlauf_widget import VerlaufWidget
from qm_app.ui.dokument_widget import DokumentWidget


class OptionalDate(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        layout=QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.check=QCheckBox('Angeben')
        self.edit=QDateEdit()
        self.edit.setCalendarPopup(True)
        self.edit.setDisplayFormat('dd.MM.yyyy')
        layout.addWidget(self.check)
        layout.addWidget(self.edit)
        self.check.toggled.connect(self.edit.setEnabled)
        self.set_value(None)

    def set_value(self,value):
        d=value or date.today()
        self.edit.setDate(QDate(d.year,d.month,d.day))
        self.check.setChecked(value is not None)
        self.edit.setEnabled(value is not None)

    def value(self):
        return self.edit.date().toPython() if self.check.isChecked() else None


class MassnahmeDialog(QDialog):
    def __init__(self,database,item=None,thema_id=None,besprechung_id=None,beschluss=None,parent=None):
        super().__init__(parent)
        self.db,self.item=database,item
        self.thema_id=item.thema_id if item else thema_id
        self.besprechung_id=item.besprechung_id if item else besprechung_id
        self.repo=MassnahmeRepository(database)
        self.setWindowTitle('Maßnahme bearbeiten' if item else 'Maßnahme anlegen')
        self.resize(850,730)
        layout=QVBoxLayout(self)
        tabs=QTabWidget()
        layout.addWidget(tabs)
        page=QWidget()
        form=QFormLayout(page)
        self.thema=QComboBox()
        for t in ThemaRepository(database).list():
            self.thema.addItem(f'{t.titel} · {str(t.id)[:8]}',str(t.id))
        if self.thema_id:
            self.thema.setCurrentIndex(self.thema.findData(str(self.thema_id)))
            self.thema.setEnabled(False)
        form.addRow('Thema *',self.thema)
        self.titel=QLineEdit()
        self.titel.setMaxLength(255)
        self.verantwortlich=QLineEdit()
        self.verantwortlich.setMaxLength(100)
        self.status=QComboBox()
        self.status.addItems(MASSNAHME_STATUS)
        self.beschreibung,self.ziel,self.begruendung=QPlainTextEdit(),QPlainTextEdit(),QPlainTextEdit()
        for field in (self.beschreibung,self.ziel,self.begruendung):
            field.setMaximumHeight(100)
        self.faellig,self.abgeschlossen=OptionalDate(),OptionalDate()
        for label,field in [('Titel *',self.titel),('Verantwortlich *',self.verantwortlich),('Status',self.status),
            ('Fällig am',self.faellig),('Abgeschlossen am',self.abgeschlossen),('Beschreibung',self.beschreibung),
            ('Ziel',self.ziel),('Begründung',self.begruendung)]:
            form.addRow(label,field)
        if self.besprechung_id:
            form.addRow(QLabel('Diese Maßnahme ist mit dem Ursprungs-TOP verknüpft.'))
        tabs.addTab(page,'Stammdaten')
        page=QWidget()
        form=QFormLayout(page)
        self.ergebnis=QComboBox()
        self.ergebnis.addItem('Nicht geprüft','')
        for value in WIRKSAMKEIT_ERGEBNIS:
            self.ergebnis.addItem(value,value)
        self.pruefung_am=OptionalDate()
        self.pruefung_durch=QLineEdit()
        self.pruefung_durch.setMaxLength(100)
        form.addRow('Ergebnis',self.ergebnis)
        form.addRow('Geprüft am',self.pruefung_am)
        form.addRow('Geprüft durch',self.pruefung_durch)
        tabs.addTab(page,'Wirksamkeitsprüfung')
        tabs.addTab(DokumentWidget(database,'massnahme',item.id if item else None),'Dokumente')
        self.history=VerlaufWidget(VerlaufRepository(database),'qm.massnahme',item.id if item else None)
        tabs.addTab(self.history,'Verlauf')
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText('Maßnahme speichern')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Schließen ohne Stammdaten zu speichern')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.populate()
        if not item and beschluss:
            self.beschreibung.setPlainText(beschluss)

    def populate(self):
        m=self.item
        if m is None:
            return
        self.titel.setText(m.titel)
        self.verantwortlich.setText(m.verantwortlich)
        self.status.setCurrentText(m.status)
        self.beschreibung.setPlainText(m.beschreibung or '')
        self.ziel.setPlainText(m.ziel or '')
        self.begruendung.setPlainText(m.begruendung or '')
        self.faellig.set_value(m.faellig_am)
        self.abgeschlossen.set_value(m.abgeschlossen_am)
        self.ergebnis.setCurrentIndex(self.ergebnis.findData(m.wirksamkeitspruefung_ergebnis or ''))
        self.pruefung_am.set_value(m.wirksamkeitspruefung_am)
        self.pruefung_durch.setText(m.wirksamkeitspruefung_durch or '')

    def accept(self):
        values=dict(thema_id=UUID(self.thema.currentData()) if self.thema.currentData() else None,
            besprechung_id=self.besprechung_id,titel=self.titel.text().strip(),verantwortlich=self.verantwortlich.text().strip(),
            status=self.status.currentText(),beschreibung=self.beschreibung.toPlainText().strip() or None,
            ziel=self.ziel.toPlainText().strip() or None,begruendung=self.begruendung.toPlainText().strip() or None,
            faellig_am=self.faellig.value(),abgeschlossen_am=self.abgeschlossen.value(),
            wirksamkeitspruefung_ergebnis=self.ergebnis.currentData() or None,
            wirksamkeitspruefung_am=self.pruefung_am.value(),wirksamkeitspruefung_durch=self.pruefung_durch.text().strip() or None)
        try:
            if self.item:
                self.repo.update(replace(self.item,**values))
            else:
                self.repo.create(Massnahme(erstellt_von=self.db.user,**values))
        except ConcurrencyError:
            QMessageBox.warning(self,'Zwischenzeitliche Änderung','Die Maßnahme wird neu geladen. Ungespeicherte Eingaben werden ersetzt; bitte erneut prüfen.')
            try:
                self.item=self.repo.get(self.item.id)
                self.populate()
                self.history.reload()
            except DatabaseError as error:
                QMessageBox.warning(self,'Laden fehlgeschlagen',str(error))
                self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
            return
        except DatabaseError as error:
            QMessageBox.warning(self,'Speichern nicht möglich',str(error))
            return
        super().accept()
