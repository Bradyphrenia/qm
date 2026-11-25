from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import re
import shutil
from uuid import UUID
import zipfile

from PySide6.QtCore import QDir, QIODevice, QLockFile, QSaveFile, QTemporaryDir
from PySide6.QtWidgets import QApplication

from qm_app.db import DatabaseError


def safe_filename(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name.replace('\\', '/').split('/')[-1]).strip(' .')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    if not name or name.split('.')[0].upper() in reserved:
        name = 'Dokument_' + name
    return name


DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
_TEMPLATE_MAIN = b'application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml'
_DOCUMENT_MAIN = b'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'


def is_word_template(name):
    # Nur makrofreie Vorlagen; .dotm behält das bisherige Öffnen-Verhalten.
    return (name or '').lower().endswith('.dotx')


def template_to_docx(data):
    """Wandelt eine Word-Vorlage (.dotx) in ein normales Dokument (.docx) um.

    Beide Formate sind identisch bis auf den Inhaltstyp des Hauptteils in [Content_Types].xml.
    Word öffnet das Ergebnis als vorhandene Datei, sodass Strg+S in die Arbeitskopie speichert.
    Trägt die Datei bereits den Dokument-Inhaltstyp (umbenannte .docx, manche LibreOffice-
    Versionen), wird sie unverändert übernommen.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as source:
            types = source.read('[Content_Types].xml')
            if _TEMPLATE_MAIN not in types:
                if _DOCUMENT_MAIN in types:
                    return data
                raise DatabaseError('Die Datei ist keine gültige Word-Vorlage (.dotx).')
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as target:
                for entry in source.infolist():
                    if entry.filename == '[Content_Types].xml':
                        target.writestr(entry, types.replace(_TEMPLATE_MAIN, _DOCUMENT_MAIN))
                    else:
                        target.writestr(entry, source.read(entry))
    except (zipfile.BadZipFile, KeyError) as error:
        raise DatabaseError('Die Datei ist keine gültige Word-Vorlage (.dotx).') from error
    return output.getvalue()


def write_download(path, data):
    output = QSaveFile(str(path))
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise DatabaseError('Die Zieldatei konnte nicht geöffnet werden: ' + output.errorString())
    if output.write(data) != len(data):
        output.cancelWriting()
        raise DatabaseError('Die Datei konnte nicht vollständig geschrieben werden.')
    if not output.commit():
        raise DatabaseError('Die Datei konnte nicht gespeichert werden: ' + output.errorString())


@dataclass
class WorkingCopy:
    document_id: UUID
    expected_version: int
    baseline_checksum: bytes
    name: str
    mime_type: str
    path: Path
    directory: QTemporaryDir
    lock: QLockFile


class WorkingCopyManager:
    def __init__(self):
        self._copies = {}
        self._cleanup_orphans()

    @staticmethod
    def _cleanup_orphans():
        for path in Path(QDir.tempPath()).glob('qm-dokument-*'):
            if not path.is_dir():
                continue
            lock = QLockFile(str(path / '.lock'))
            if lock.tryLock(0):
                lock.unlock()
                try:
                    shutil.rmtree(path)
                except OSError:
                    pass

    def get(self, document_id):
        return self._copies.get(document_id)

    def create(self, snapshot):
        existing = self.get(snapshot.id)
        if existing is not None:
            return existing
        directory = QTemporaryDir(QDir.tempPath() + '/qm-dokument-XXXXXX')
        if not directory.isValid():
            raise DatabaseError('Temporäre Datei konnte nicht angelegt werden.')
        lock = QLockFile(str(Path(directory.path()) / '.lock'))
        if not lock.tryLock(0):
            directory.remove()
            raise DatabaseError('Temporäre Arbeitskopie konnte nicht gesperrt werden.')
        path = Path(directory.path()) / safe_filename(snapshot.name)
        write_download(path, snapshot.data)
        copy = WorkingCopy(
            document_id=snapshot.id,
            expected_version=snapshot.version,
            baseline_checksum=bytes(snapshot.checksum),
            name=snapshot.name,
            mime_type=snapshot.mime_type,
            path=path,
            directory=directory,
            lock=lock,
        )
        self._copies[snapshot.id] = copy
        return copy

    def read_if_changed(self, copy, limit):
        try:
            before = copy.path.stat()
            if before.st_size > limit:
                raise DatabaseError(f'Die Datei überschreitet das Upload-Limit von {limit // (1024 * 1024)} MB.')
            with copy.path.open('rb') as source:
                data = source.read(limit + 1)
            after = copy.path.stat()
        except OSError as error:
            raise DatabaseError('Die Arbeitskopie konnte nicht gelesen werden. Bitte im externen Programm speichern oder schließen.') from error
        if len(data) > limit:
            raise DatabaseError(f'Die Datei überschreitet das Upload-Limit von {limit // (1024 * 1024)} MB.')
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise DatabaseError('Die Arbeitskopie wurde während des Einlesens verändert. Bitte erneut versuchen.')
        return None if hashlib.sha256(data).digest() == copy.baseline_checksum else data

    def discard(self, document_id):
        copy = self._copies.pop(document_id, None)
        if copy is not None:
            copy.lock.unlock()
            copy.directory.remove()

    def cleanup(self):
        for document_id in list(self._copies):
            self.discard(document_id)


def working_copy_manager():
    app = QApplication.instance()
    if app is None:
        raise DatabaseError('Die Anwendung ist noch nicht initialisiert.')
    manager = getattr(app, 'qm_working_copy_manager', None)
    if manager is None:
        manager = WorkingCopyManager()
        app.qm_working_copy_manager = manager
        app.aboutToQuit.connect(manager.cleanup)
    return manager
