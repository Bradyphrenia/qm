from dataclasses import replace
from datetime import date,timedelta
from uuid import uuid4
from unittest.mock import MagicMock
import hashlib
import pytest
from PySide6.QtCore import Qt,QSettings
from PySide6.QtWidgets import QMessageBox,QFileDialog,QInputDialog,QDialog
from qm_app.config import Settings
from qm_app.db import DatabaseError,ConcurrencyError
from qm_app.models import Thema,Sitzung,Besprechung,Massnahme
from qm_app.repositories.thema_repo import ThemaRepository
from qm_app.repositories.sitzung_repo import SitzungRepository
from qm_app.repositories.besprechung_repo import BesprechungRepository
from qm_app.repositories.massnahme_repo import MassnahmeRepository
from qm_app.repositories.dokument_repo import DokumentRepository,ENTITIES
from qm_app.repositories.verlauf_repo import VerlaufRepository
from qm_app.ui.massnahme_dialog import MassnahmeDialog
from qm_app.ui.massnahme_view import MassnahmeModel,MassnahmeFilter,overdue
from qm_app.ui.table_model import Column
from qm_app.ui.dokument_widget import DokumentWidget,read_upload,safe_filename,write_download


@pytest.fixture(autouse=True)
def no_blocking_warning(monkeypatch):
    def fail(parent,title,message):
        pytest.fail(f'Unerwarteter Dialog: {title}: {message}')
    monkeypatch.setattr(QMessageBox,'warning',fail)


@pytest.fixture
def workflow(database):
    topic=ThemaRepository(database).create(Thema(titel='[AUTOTEST] Gesamtprozess',kategorie='Test',erstellt_von='ignored'))
    session=SitzungRepository(database).create(Sitzung(bezeichnung='[AUTOTEST] QM',datum=date.today(),erstellt_von='ignored'))
    top=BesprechungRepository(database).create(Besprechung(sitzung_id=session,thema_id=topic,status='beschlossen',beschluss='Ablauf verbessern',erstellt_von='ignored'))
    m=Massnahme(thema_id=topic,besprechung_id=top,titel='[AUTOTEST] Verbesserung',verantwortlich='Testrolle',erstellt_von='ignored',faellig_am=date.today()-timedelta(days=1))
    measure=MassnahmeRepository(database).create(m)
    return {'thema':topic,'sitzung':session,'besprechung':top,'massnahme':measure}


def test_measure_lifecycle_and_audit(database,workflow):
    repo=MassnahmeRepository(database)
    original=repo.get(workflow['massnahme'])
    assert original.erstellt_von==database.user and overdue(original)
    assert original.id in {m.id for m in repo.list(workflow['thema'])}
    with pytest.raises(DatabaseError,match='begründen'):
        repo.update(replace(original,faellig_am=date.today()+timedelta(days=1)))
    repo.update(replace(original,status='umgesetzt',abgeschlossen_am=date.today()))
    implemented=repo.get(original.id)
    assert not overdue(implemented)
    with pytest.raises(ConcurrencyError):
        repo.update(original)
    with pytest.raises(DatabaseError):
        repo.update(replace(implemented,status='wirksam'))
    repo.update(replace(implemented,status='wirksam',wirksamkeitspruefung_ergebnis='wirksam',
        wirksamkeitspruefung_am=date.today(),wirksamkeitspruefung_durch='Testprüfer'))
    checked=repo.get(original.id)
    assert checked.version==original.version+2
    with pytest.raises(DatabaseError,match='begründen'):
        repo.update(replace(checked,status='in_bearbeitung'))
    events=VerlaufRepository(database).list('qm.massnahme',original.id)
    assert len(events)==3
    assert events[0].neue_werte['wirksamkeitspruefung_ergebnis']=='wirksam'


def test_measure_origin_and_validation(database,workflow):
    repo=MassnahmeRepository(database)
    m=repo.get(workflow['massnahme'])
    other=ThemaRepository(database).create(Thema(titel='[AUTOTEST] anderes Thema',kategorie='Test',erstellt_von='ignored'))
    with pytest.raises(DatabaseError,match='TOP'):
        repo.create(replace(m,id=None,thema_id=other))
    with pytest.raises(DatabaseError):
        repo.update(replace(m,thema_id=other))
    with pytest.raises(DatabaseError):
        repo.create(replace(m,titel=' '))
    with pytest.raises(DatabaseError):
        repo.update(replace(m,status='abgebrochen'))
    repo.update(replace(m,status='abgebrochen',begruendung='Nicht mehr erforderlich'))


def test_document_upload_download_all_links_and_versions(database,workflow):
    repo=DokumentRepository(database)
    payload=b'QM\x00\xff\n'+ 'Qualitätsprüfung'.encode()
    id=repo.upload('Muster.bin','application/octet-stream',payload,'thema',workflow['thema'],dokumenttyp='Nachweis')
    doc=repo.get(id)
    assert doc.version==1 and doc.dateigroesse==len(payload)
    assert bytes(doc.pruefsumme_sha256)==hashlib.sha256(payload).digest()
    assert repo.download(id)==('Muster.bin',payload)
    assert not hasattr(repo.list('thema',workflow['thema'])[0],'inhalt')
    for entity in ('sitzung','besprechung','massnahme'):
        repo.link(id,entity,workflow[entity])
        assert id in {d.id for d in repo.list(entity,workflow[entity])}
    with pytest.raises(DatabaseError,match='bereits vorhanden'):
        repo.link(id,'thema',workflow['thema'])
    repo.set_status(id,doc.version,'freigegeben')
    released=repo.get(id)
    assert released.version==2
    assert released.freigegeben_am and released.freigegeben_von==database.user
    with pytest.raises(ConcurrencyError):
        repo.set_status(id,doc.version,'archiviert')
    with pytest.raises(DatabaseError,match='Freigegebene'):
        repo.delete(id,released.version)
    # Verify actual database trigger, beyond the application's precheck.
    with pytest.raises(DatabaseError):
        with database.transaction() as c:
            c.execute('DELETE FROM qm.dokument WHERE id=%s',(id,))
    next_id=repo.new_version(id,released.version,'Muster_v2.bin','application/octet-stream',b'next')
    successor=repo.get(next_id)
    assert successor.vorgaenger_dokument_id==id
    assert successor.dokument_gruppe_id==doc.dokument_gruppe_id
    assert successor.version==released.version+1 and successor.status=='entwurf'
    assert successor.freigegeben_von is None
    for entity in ENTITIES:
        assert next_id in {d.id for d in repo.list(entity,workflow[entity])}
    with pytest.raises(DatabaseError,match='Nachfolgeversion'):
        repo.new_version(id,released.version,'branch.txt','text/plain',b'no')
    assert repo.download(id)[1]==payload
    repo.unlink(next_id,'thema',workflow['thema'])
    assert next_id not in {d.id for d in repo.list('thema',workflow['thema'])}
    assert repo.download(next_id)[1]==b'next'
    repo.delete(next_id,successor.version)
    with pytest.raises(DatabaseError):
        repo.get(next_id)


def test_document_transaction_rollback_and_limits(database,workflow):
    repo=DokumentRepository(database)
    before={d.id for d in repo.list()}
    with pytest.raises(DatabaseError):
        repo.upload('rollback.txt','text/plain',b'test','thema',uuid4())
    assert {d.id for d in repo.list()}==before
    with pytest.raises(DatabaseError,match='Limit'):
        repo.upload('too-big.txt','text/plain',b'12345','thema',workflow['thema'],limit=4)
    with pytest.raises(DatabaseError):
        repo.upload('bad.txt','text/plain',b'x','untrusted; DROP TABLE',workflow['thema'])
    assert {d.id for d in repo.list()}==before


def test_legacy_document_without_group(database,workflow):
    repo=DokumentRepository(database)
    id=repo.upload('legacy.txt','text/plain',b'old','thema',workflow['thema'])
    with database.transaction() as c:
        c.execute('UPDATE qm.dokument SET dokument_gruppe_id=NULL WHERE id=%s',(id,))
    child=repo.new_version(id,1,'new.txt','text/plain',b'new')
    assert repo.get(child).dokument_gruppe_id==id


def test_measure_filters_and_highlight(app):
    m=Massnahme(thema_id=uuid4(),titel='Test',verantwortlich='QM-Team',erstellt_von='test',faellig_am=date.today()-timedelta(days=1))
    model=MassnahmeModel([Column('titel','Titel')],[m,replace(m,status='wirksam',abgeschlossen_am=date.today())])
    assert model.data(model.index(0,0),Qt.ItemDataRole.BackgroundRole) is not None
    assert model.data(model.index(1,0),Qt.ItemDataRole.BackgroundRole) is None
    proxy=MassnahmeFilter()
    proxy.setSourceModel(model)
    proxy.set_filters('offen','qm-team')
    assert proxy.rowCount()==1
    proxy.set_filters('offen','andere')
    assert proxy.rowCount()==0


def test_local_files_and_upload_limit(tmp_path):
    source=tmp_path/'source.txt'
    source.write_bytes(b'12345')
    with pytest.raises(DatabaseError):
        read_upload(source,4)
    name,mime,data=read_upload(source,5)
    assert name=='source.txt' and mime=='text/plain'
    destination=tmp_path/'download.txt'
    write_download(destination,data)
    assert destination.read_bytes()==b'12345'
    assert safe_filename('../../bad.txt')=='bad.txt'
    assert '/' not in safe_filename(r'C:\folder\bad.txt')
    assert safe_filename('CON.txt').startswith('Dokument_')
    settings=Settings(QSettings(str(tmp_path/'config.ini'),QSettings.Format.IniFormat))
    assert settings.upload_limit_mb()==25
    settings.save_upload_limit(5)
    assert settings.upload_limit_mb()==5


def test_measure_dialog_real_save(app,database,workflow):
    dialog=MassnahmeDialog(database,thema_id=workflow['thema'],besprechung_id=workflow['besprechung'],beschluss='Testbeschluss')
    assert dialog.beschreibung.toPlainText()=='Testbeschluss'
    dialog.titel.setText('[AUTOTEST] Dialogmaßnahme')
    dialog.verantwortlich.setText('Testrolle')
    dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted
    assert any(m.titel=='[AUTOTEST] Dialogmaßnahme' for m in MassnahmeRepository(database).list(workflow['thema']))
    dialog.close()


def test_document_widget_upload_download_and_search(app,database,workflow,tmp_path,monkeypatch):
    path=tmp_path/'UI_Muster.txt'
    path.write_bytes('Prüfdatei'.encode())
    widget=DokumentWidget(database,'thema',workflow['thema'])
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args,**kwargs:(str(path),''))
    monkeypatch.setattr(QInputDialog,'getText',lambda *args,**kwargs:('Test',True))
    widget.upload()
    assert widget.model.rowCount()==1
    widget.table.selectRow(0)
    assert 'SHA-256' in widget.details.text()
    target=tmp_path/'out.txt'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(target),''))
    widget.download()
    assert target.read_bytes()==path.read_bytes()
    widget.search.setText('ui_muster')
    assert widget.proxy.rowCount()==1
    widget.search.setText('nicht vorhanden')
    assert widget.proxy.rowCount()==0
    assert not widget.buttons['download'].isEnabled()
    widget.close()


def test_complete_workflow_references(database,workflow):
    documents=DokumentRepository(database)
    id=documents.upload('Nachweis.txt','text/plain',b'Umsetzung dokumentiert','massnahme',workflow['massnahme'])
    m=MassnahmeRepository(database).get(workflow['massnahme'])
    top=BesprechungRepository(database).get(m.besprechung_id)
    assert top.thema_id==m.thema_id==workflow['thema']
    assert top.sitzung_id==workflow['sitzung']
    assert documents.list('massnahme',m.id)[0].id==id
    assert VerlaufRepository(database).list('qm.massnahme',m.id)


def test_document_open_retains_temporary_copy(app,database,workflow,monkeypatch):
    from pathlib import Path
    from PySide6.QtGui import QDesktopServices
    repo=DokumentRepository(database)
    id=repo.upload('Open.txt','text/plain',b'open payload','thema',workflow['thema'])
    widget=DokumentWidget(database,'thema',workflow['thema'])
    widget.reload()
    widget.table.selectRow(0)
    urls=[]
    monkeypatch.setattr(QDesktopServices,'openUrl',lambda url: urls.append(url) or True)
    widget.open_document()
    widget.close()
    assert Path(urls[0].toLocalFile()).read_bytes()==b'open payload'
    for directory in app.qm_open_document_dirs:
        directory.remove()
    app.qm_open_document_dirs=[]


def test_measure_dialog_conflict_reloads(app,database,workflow,monkeypatch):
    monkeypatch.setattr(QMessageBox,'warning',MagicMock())
    repo=MassnahmeRepository(database)
    item=repo.get(workflow['massnahme'])
    dialog=MassnahmeDialog(database,item=item)
    repo.update(replace(item,titel='Parallel geändert'))
    dialog.titel.setText('Veraltete Eingabe')
    dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Rejected
    assert dialog.titel.text()=='Parallel geändert'
    assert dialog.item.version==item.version+1
    dialog.close()


def test_document_widget_status_and_version(app,database,workflow,tmp_path,monkeypatch):
    widget=DokumentWidget(database,'thema',workflow['thema'])
    repo=DokumentRepository(database)
    id=repo.upload('first.txt','text/plain',b'first','thema',workflow['thema'])
    widget.reload()
    widget.table.selectRow(0)
    monkeypatch.setattr(QInputDialog,'getItem',lambda *args,**kwargs:('freigegeben',True))
    widget.change_status()
    assert repo.get(id).status=='freigegeben'
    widget.table.selectRow(0)
    path=tmp_path/'second.txt'
    path.write_bytes(b'second')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args,**kwargs:(str(path),''))
    widget.new_version()
    assert len(widget.model.rows)==2
    child=next(d for d in widget.model.rows if d.id!=id)
    assert child.vorgaenger_dokument_id==id
    assert repo.download(child.id)[1]==b'second'
    widget.close()
