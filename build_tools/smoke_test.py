"""Offline self-check for compiled/frozen applications; never touches a DB."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import importlib
import io
import json
import os
import zipfile


def run():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from main import application_icon_path, configure_application
    from qm_app.models import Thema, Massnahme
    from qm_app.config import ConnectionProfile
    from qm_app.ui.main_window import MainWindow
    from qm_app.ui.login_dialog import LoginDialog
    from qm_app.ui.thema_dialog import ThemaDialog
    from qm_app.ui.sitzung_dialog import SitzungDialog
    from qm_app.ui.massnahme_dialog import MassnahmeDialog
    from qm_app.ui.agenda_widget import AgendaDialog
    from qm_app.ui.dokument_widget import DokumentWidget
    from qm_app.document_working_copy import is_word_template, template_to_docx
    from qm_app.repositories.thema_repo import ThemaRepository
    from qm_app.repositories.verlauf_repo import VerlaufRepository

    class Cursor:
        def execute(self, *args, **kwargs):
            pass
        def fetchall(self):
            return []

    class OfflineDB:
        user = 'Build-Selbsttest'
        @contextmanager
        def transaction(self):
            yield Cursor()

    class OfflineSettings:
        def load_profile(self):
            return ConnectionProfile()

    application = QApplication.instance() or QApplication([])
    configure_application(application)
    assert application_icon_path().is_file()
    assert not application.windowIcon().isNull()
    # Qt-Standardtexte (Ja/Nein usw.) müssen deutsch sein; prüft auch, dass die .qm-Dateien gebündelt sind.
    from PySide6.QtCore import QCoreApplication
    assert QCoreApplication.translate('QPlatformTheme', '&Yes') != '&Yes', 'Deutsche Qt-Übersetzung fehlt'
    db = OfflineDB()
    topic = Thema(titel='Build-Test', kategorie='Test', erstellt_von=db.user)
    assert replace(topic, titel='Geändert').titel == 'Geändert'
    assert 'titel' in Thema.__dataclass_fields__
    assert Massnahme.__dataclass_fields__
    # Prove we loaded binary modules rather than accidentally bundling source.
    for name in ('qm_app.models', 'qm_app.ui.main_window', 'qm_app.repositories.dokument_repo',
                 'qm_app.ui.dokument_widget', 'qm_app.document_working_copy'):
        origin = importlib.import_module(name).__file__
        assert origin.endswith(('.so', '.pyd')), origin
    # Vorlagen-Umwandlung (.dotx -> .docx) offline im kompilierten Modul prüfen.
    template = io.BytesIO()
    with zipfile.ZipFile(template, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types><Override PartName="/word/document.xml" ContentType='
            '"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"/></Types>')
        archive.writestr('word/document.xml', '<w:document/>')
    assert is_word_template('Protokoll.dotx') and not is_word_template('Protokoll.dotm')
    converted = zipfile.ZipFile(io.BytesIO(template_to_docx(template.getvalue())))
    assert b'document.main+xml' in converted.read('[Content_Types].xml')
    windows = [MainWindow(db), LoginDialog(settings=OfflineSettings()),
        ThemaDialog(ThemaRepository(db), VerlaufRepository(db)),
        SitzungDialog(db), MassnahmeDialog(db), AgendaDialog(db, None), DokumentWidget(db)]
    for window in windows:
        window.show()
        application.processEvents()
        assert window.isVisible()
        window.close()
    # Explicit destruction while QApplication is alive prevents teardown races.
    import shiboken6
    for window in windows:
        shiboken6.delete(window)
    application.processEvents()
    marker = os.environ.get('QM_SMOKE_RESULT')
    if marker:
        Path(marker).write_text(json.dumps({'ok': True, 'windows': len(windows)}), encoding='utf-8')
    application.closeAllWindows()
    application.quit()


if __name__ == '__main__':
    run()
