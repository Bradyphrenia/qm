from contextlib import contextmanager
from pathlib import Path
import mimetypes
import re
from uuid import UUID
from PySide6.QtCore import Qt, QSortFilterProxyModel, QTemporaryDir, QUrl, QSaveFile, QIODevice
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,
    QTableView,QAbstractItemView,QFileDialog,QInputDialog,QMessageBox,QDialog,
    QDialogButtonBox,QComboBox,QFormLayout,QApplication)
from qm_app.config import Settings
from qm_app.db import DatabaseError
from qm_app.models import DOKUMENT_STATUS
from qm_app.repositories.dokument_repo import DokumentRepository, ENTITIES
from qm_app.ui.table_model import TableModel, Column


@contextmanager
def busy():
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name.replace('\\','/').split('/')[-1]).strip(' .')
    if not name or name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
        name = 'Dokument_' + name
    return name


def read_upload(path, limit):
    with open(path, 'rb') as f:
        data = f.read(limit+1)
    if len(data) > limit:
        raise DatabaseError(f'Die Datei überschreitet das Upload-Limit von {limit//(1024*1024)} MB.')
    return Path(path).name, mimetypes.guess_type(path)[0] or 'application/octet-stream', data


def write_download(path, data):
    output = QSaveFile(str(path))
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise DatabaseError('Die Zieldatei konnte nicht geöffnet werden: '+output.errorString())
    if output.write(data) != len(data):
        output.cancelWriting()
        raise DatabaseError('Die Datei konnte nicht vollständig geschrieben werden.')
    if not output.commit():
        raise DatabaseError('Die Datei konnte nicht gespeichert werden: '+output.errorString())


class TargetDialog(QDialog):
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle('Dokument zuordnen')
        layout = QFormLayout(self)
        self.entity, self.target = QComboBox(), QComboBox()
        self.target.setMinimumWidth(450)
        for key, label in ENTITIES.items():
            self.entity.addItem(label,key)
        layout.addRow('Bereich',self.entity)
        layout.addRow('Datensatz',self.target)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.entity.currentIndexChanged.connect(self.reload)
        self.reload()

    def reload(self):
        self.target.clear()
        try:
            for row in self.repo.targets(self.entity.currentData()):
                self.target.addItem(f"{row['label']} · {str(row['id'])[:8]}",str(row['id']))
        except DatabaseError as error:
            QMessageBox.warning(self,'Laden fehlgeschlagen',str(error))

    def accept(self):
        if not self.target.currentData():
            QMessageBox.warning(self,'Zuordnung fehlt','Bitte einen vorhandenen Datensatz auswählen.')
            return
        super().accept()


class DokumentWidget(QWidget):
    def __init__(self,database,entity=None,entity_id=None,parent=None):
        super().__init__(parent)
        self.repo=DokumentRepository(database)
        self.entity,self.entity_id=entity,entity_id
        self.loaded=False
        layout=QVBoxLayout(self)
        self.notice=QLabel('Dokumentaktionen werden sofort gespeichert, unabhängig vom umgebenden Dialog.')
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.search=QLineEdit()
        self.search.setPlaceholderText('Dateiname suchen …')
        layout.addWidget(self.search)
        bar=QHBoxLayout()
        self.buttons={}
        for key,label,handler in [('upload','Hochladen',self.upload),('version','Neue Version',self.new_version),
            ('download','Speichern unter',self.download),('open','Öffnen',self.open_document)]:
            button=QPushButton(label)
            button.clicked.connect(handler)
            self.buttons[key]=button
            bar.addWidget(button)
        layout.addLayout(bar)
        bar=QHBoxLayout()
        for key,label,handler in [('link','Zuordnen',self.link),('unlink','Zuordnung lösen',self.unlink),
            ('status','Status ändern',self.change_status),('refresh','Aktualisieren',self.reload),('limit','Upload-Limit',self.change_limit)]:
            button=QPushButton(label)
            button.clicked.connect(handler)
            self.buttons[key]=button
            bar.addWidget(button)
        layout.addLayout(bar)
        self.model=TableModel([Column('dateiname','Dateiname'),Column('dokumenttyp','Typ'),Column('status','Status'),
            Column('version','Version / Stand'),Column('dateigroesse','Bytes'),Column('erstellt_am','Erstellt')])
        self.proxy=QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(self.model.SortRole)
        self.proxy.setFilterKeyColumn(0)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.table=QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(5,Qt.SortOrder.DescendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.details=QLabel()
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.details)
        self.message=QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        if entity and entity_id is None:
            self.notice.setText('Bitte den Datensatz zuerst speichern und erneut öffnen, um Dokumente zu verwalten.')
        self.selection_changed()

    def showEvent(self,event):
        super().showEvent(event)
        if not self.loaded:
            self.reload()

    def selected(self):
        rows=self.table.selectionModel().selectedRows()
        return self.model.rows[self.proxy.mapToSource(rows[0]).row()] if rows else None

    def selection_changed(self,*args):
        selected=self.selected()
        available=not self.entity or self.entity_id is not None
        for key,button in self.buttons.items():
            button.setEnabled(available and (key in ('upload','refresh','limit') or selected is not None))
        self.buttons['unlink'].setEnabled(selected is not None and self.entity_id is not None)
        if selected:
            checksum=bytes(selected.pruefsumme_sha256).hex() if selected.pruefsumme_sha256 else 'nicht vorhanden'
            self.details.setText(f'SHA-256: {checksum}\nGruppe: {selected.dokument_gruppe_id or selected.id}\n'
                f'Vorgänger: {selected.vorgaenger_dokument_id or "–"} | Freigabe: {selected.freigegeben_von or "–"}')
        else:
            self.details.clear()

    def reload(self):
        try:
            with busy():
                rows=[] if self.entity and self.entity_id is None else self.repo.list(self.entity,self.entity_id)
            self.model.set_rows(rows)
            self.table.resizeColumnsToContents()
            self.table.setColumnWidth(0,260)
            self.message.setText(f'{len(rows)} Dokumente · Upload-Limit {Settings().upload_limit_mb()} MB')
            self.loaded=True
        except DatabaseError as error:
            self.message.setText(str(error))
        self.selection_changed()

    def run(self, action):
        try:
            with busy():
                action()
        except (DatabaseError,OSError) as error:
            QMessageBox.warning(self,'Dokumentaktion fehlgeschlagen',str(error))
        self.reload()

    def choose_target(self):
        dialog=TargetDialog(self.repo,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:
            return None
        return dialog.entity.currentData(),UUID(dialog.target.currentData())

    def upload(self):
        target=(self.entity,self.entity_id) if self.entity else self.choose_target()
        if not target:
            return
        path,_=QFileDialog.getOpenFileName(self,'Dokument hochladen')
        if not path:
            return
        kind,ok=QInputDialog.getText(self,'Dokumenttyp','Dokumenttyp (optional):')
        if not ok:
            return
        limit=Settings().upload_limit_mb()*1024*1024
        def action():
            name,mime,data=read_upload(path,limit)
            self.repo.upload(name,mime,data,*target,dokumenttyp=kind.strip() or None,limit=limit)
        self.run(action)

    def new_version(self):
        item=self.selected()
        if not item:
            return
        path,_=QFileDialog.getOpenFileName(self,'Neue Dokumentversion auswählen')
        if not path:
            return
        limit=Settings().upload_limit_mb()*1024*1024
        def action():
            name,mime,data=read_upload(path,limit)
            self.repo.new_version(item.id,item.version,name,mime,data,limit=limit)
        self.run(action)

    def download(self):
        item=self.selected()
        if not item:
            return
        path,_=QFileDialog.getSaveFileName(self,'Dokument speichern',safe_filename(item.dateiname))
        if path:
            self.run(lambda: write_download(path,self.repo.download(item.id)[1]))

    def open_document(self):
        item=self.selected()
        if not item:
            return
        def action():
            name,data=self.repo.download(item.id)
            directory=QTemporaryDir()
            if not directory.isValid():
                raise DatabaseError('Temporäre Datei konnte nicht angelegt werden.')
            path=Path(directory.path())/safe_filename(name)
            write_download(path,data)
            # Keep files alive even after closing the parent dialog.
            app=QApplication.instance()
            if not hasattr(app,'qm_open_document_dirs'):
                app.qm_open_document_dirs=[]
            app.qm_open_document_dirs.append(directory)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise DatabaseError('Kein passendes Programm zum Öffnen gefunden. Bitte „Speichern unter“ verwenden.')
        self.run(action)

    def link(self):
        item=self.selected()
        if not item:
            return
        target=self.choose_target()
        if target:
            self.run(lambda: self.repo.link(item.id,*target))

    def unlink(self):
        item=self.selected()
        if item and QMessageBox.question(self,'Zuordnung lösen','Nur die Zuordnung zu diesem Datensatz lösen? Die Datei bleibt erhalten.')==QMessageBox.StandardButton.Yes:
            self.run(lambda: self.repo.unlink(item.id,self.entity,self.entity_id))

    def change_status(self):
        item=self.selected()
        if not item:
            return
        status,ok=QInputDialog.getItem(self,'Dokumentstatus','Neuer Status:',DOKUMENT_STATUS,DOKUMENT_STATUS.index(item.status),False)
        if ok:
            self.run(lambda: self.repo.set_status(item.id,item.version,status))

    def change_limit(self):
        settings=Settings()
        limit,ok=QInputDialog.getInt(self,'Upload-Limit','Maximale Dateigröße in MB:',settings.upload_limit_mb(),1,1024)
        if ok:
            settings.save_upload_limit(limit)
            self.reload()
