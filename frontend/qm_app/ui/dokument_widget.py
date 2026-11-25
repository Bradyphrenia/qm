from contextlib import contextmanager
from datetime import date
from pathlib import Path
import mimetypes
from uuid import UUID
from PySide6.QtCore import Qt, QSortFilterProxyModel, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,
    QTableView,QAbstractItemView,QFileDialog,QInputDialog,QMessageBox,QDialog,
    QDialogButtonBox,QComboBox,QFormLayout,QApplication)
from qm_app.config import Settings
from qm_app.db import DatabaseError
from qm_app.document_working_copy import (DOCX_MIME, is_word_template, safe_filename, template_to_docx,
    working_copy_manager, write_download)
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


def read_upload(path, limit):
    with open(path, 'rb') as f:
        data = f.read(limit+1)
    if len(data) > limit:
        raise DatabaseError(f'Die Datei überschreitet das Upload-Limit von {limit//(1024*1024)} MB.')
    return Path(path).name, mimetypes.guess_type(path)[0] or 'application/octet-stream', data


STATUS_FILTER_ACTIVE = '__aktuell__'
INACTIVE_STATUS = ('archiviert', 'obsolet')


class DokumentFilter(QSortFilterProxyModel):
    """Kombiniert Dateinamensuche und Statusauswahl; blendet standardmäßig archivierte und obsolete Dokumente aus."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.status, self.text = STATUS_FILTER_ACTIVE, ''

    def set_filters(self, status, text):
        self.status, self.text = status, text.strip().casefold()
        self.invalidate()

    def filterAcceptsRow(self, row, parent):
        item = self.sourceModel().rows[row]
        if self.status == STATUS_FILTER_ACTIVE:
            status_ok = item.status not in INACTIVE_STATUS
        else:
            status_ok = not self.status or item.status == self.status
        return status_ok and self.text in (item.dateiname or '').casefold()


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
        self.working_copies=working_copy_manager()
        self.entity,self.entity_id=entity,entity_id
        self.loaded=False
        layout=QVBoxLayout(self)
        self.notice=QLabel('Dokumentaktionen werden sofort gespeichert, unabhängig vom umgebenden Dialog.')
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        bar=QHBoxLayout()
        self.status=QComboBox()
        self.status.addItem('Aktuelle (ohne archiviert/obsolet)',STATUS_FILTER_ACTIVE)
        self.status.addItem('Alle Status','')
        for status in DOKUMENT_STATUS:
            self.status.addItem(status,status)
        self.search=QLineEdit()
        self.search.setPlaceholderText('Dateiname suchen …')
        bar.addWidget(self.status)
        bar.addWidget(self.search)
        layout.addLayout(bar)
        bar=QHBoxLayout()
        self.buttons={}
        for key,label,handler in [('upload','Hochladen',self.upload),('version','Neue Version',self.new_version),
            ('download','Speichern unter',self.download),('open','Öffnen',self.open_document),
            ('accept','Bearbeitete Arbeitskopie übernehmen',self.accept_working_copy)]:
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
        self.proxy=DokumentFilter(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(self.model.SortRole)
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
        self.search.textChanged.connect(self.filter)
        self.status.currentIndexChanged.connect(self.filter)
        if entity and entity_id is None:
            self.notice.setText('Bitte den Datensatz zuerst speichern und erneut öffnen, um Dokumente zu verwalten.')
        self.selection_changed()

    def select_document(self, document_id):
        for row, document in enumerate(self.model.rows):
            if document.id == document_id:
                proxy_index=self.proxy.mapFromSource(self.model.index(row,0))
                if proxy_index.isValid():
                    self.table.selectRow(proxy_index.row())
                return

    def showEvent(self,event):
        super().showEvent(event)
        if not self.loaded:
            self.reload()

    def filter(self,*args):
        self.proxy.set_filters(self.status.currentData(),self.search.text())
        self.update_count()
        self.selection_changed()

    def update_count(self):
        total,shown=len(self.model.rows),self.proxy.rowCount()
        count=f'{total} Dokumente' if shown==total else f'{shown} von {total} Dokumenten angezeigt'
        self.message.setText(f'{count} · Upload-Limit {Settings().upload_limit_mb()} MB')

    def selected(self):
        rows=self.table.selectionModel().selectedRows()
        return self.model.rows[self.proxy.mapToSource(rows[0]).row()] if rows else None

    def selection_changed(self,*args):
        selected=self.selected()
        available=not self.entity or self.entity_id is not None
        for key,button in self.buttons.items():
            button.setEnabled(available and (key in ('upload','refresh','limit') or selected is not None))
        self.buttons['unlink'].setEnabled(selected is not None and self.entity_id is not None)
        self.buttons['accept'].setEnabled(selected is not None and self.working_copies.get(selected.id) is not None)
        if selected:
            checksum=bytes(selected.pruefsumme_sha256).hex() if selected.pruefsumme_sha256 else 'nicht vorhanden'
            working = '\nArbeitskopie: geöffnet' if self.working_copies.get(selected.id) is not None else ''
            self.details.setText(f'SHA-256: {checksum}\nGruppe: {selected.dokument_gruppe_id or selected.id}\n'
                f'Vorgänger: {selected.vorgaenger_dokument_id or "–"} | Freigabe: {selected.freigegeben_von or "–"}{working}')
        else:
            self.details.clear()

    def reload(self):
        try:
            with busy():
                rows=[] if self.entity and self.entity_id is None else self.repo.list(self.entity,self.entity_id)
            self.model.set_rows(rows)
            self.table.resizeColumnsToContents()
            self.table.setColumnWidth(0,260)
            self.update_count()
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
            self.repo.new_version(item.id,item.version,name,mime,data,limit=limit,
                expected_checksum=item.pruefsumme_sha256)
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
        if is_word_template(item.dateiname):
            self.create_from_template(item)
        else:
            self.open_working_copy(item.id,item.version)

    def create_from_template(self,item):
        answer=QMessageBox.question(self,'Neues Dokument aus Vorlage',
            f'Aus der Vorlage „{item.dateiname}“ ein neues Word-Dokument erstellen, sofort speichern und öffnen?\n\n'
            'Die Vorlage selbst bleibt unverändert. Zum Pflegen der Vorlage „Speichern unter“ und „Neue Version“ verwenden.')
        if answer!=QMessageBox.StandardButton.Yes:
            return
        target=(self.entity,self.entity_id) if self.entity else self.choose_target()
        if not target:
            return
        limit=Settings().upload_limit_mb()*1024*1024
        name=f'{Path(safe_filename(item.dateiname)).stem}_{date.today().isoformat()}.docx'
        try:
            with busy():
                data=template_to_docx(self.repo.download(item.id)[1])
                new_id=self.repo.upload(name,DOCX_MIME,data,*target,limit=limit)
                document=self.repo.get(new_id)
        except (DatabaseError,OSError) as error:
            QMessageBox.warning(self,'Dokumentaktion fehlgeschlagen',str(error))
            return
        self.reload()
        self.select_document(new_id)
        self.open_working_copy(document.id,document.version)

    def open_working_copy(self,document_id,version):
        try:
            with busy():
                copy=self.working_copies.get(document_id)
                if copy is None:
                    copy=self.working_copies.create(self.repo.checkout(document_id,version))
                opened=QDesktopServices.openUrl(QUrl.fromLocalFile(str(copy.path)))
            if not opened:
                raise DatabaseError('Kein passendes Programm zum Öffnen gefunden. Bitte „Speichern unter“ verwenden.')
        except (DatabaseError,OSError) as error:
            QMessageBox.warning(self,'Dokumentaktion fehlgeschlagen',str(error))
        self.selection_changed()

    def accept_working_copy(self):
        item=self.selected()
        copy=self.working_copies.get(item.id) if item else None
        if copy is None:
            return
        limit=Settings().upload_limit_mb()*1024*1024
        try:
            with busy():
                data=self.working_copies.read_if_changed(copy,limit)
            if data is None:
                QMessageBox.information(self,'Keine Änderung','Die Arbeitskopie stimmt unverändert mit dem geöffneten Datenbankstand überein.')
                return
            answer=QMessageBox.question(self,'Bearbeitete Arbeitskopie übernehmen',
                'Die bearbeitete Datei als neue Entwurfsversion speichern und die bisherige Version archivieren?')
            if answer!=QMessageBox.StandardButton.Yes:
                return
            with busy():
                new_id=self.repo.new_version(copy.document_id,copy.expected_version,copy.name,copy.mime_type,data,
                    limit=limit,expected_checksum=copy.baseline_checksum)
            self.working_copies.discard(copy.document_id)
            QMessageBox.information(self,'Dokument übernommen','Die neue Entwurfsversion wurde gespeichert und der Vorgänger archiviert.')
        except (DatabaseError,OSError) as error:
            QMessageBox.warning(self,'Dokumentaktion fehlgeschlagen',str(error))
            new_id=None
        self.reload()
        if new_id is not None:
            self.select_document(new_id)

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
