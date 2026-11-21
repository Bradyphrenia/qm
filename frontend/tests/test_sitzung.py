from dataclasses import replace
from datetime import date, time
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QDialog
from qm_app.db import DatabaseError, ConcurrencyError
from qm_app.models import Sitzung, SitzungTeilnehmer, Thema, Besprechung
from qm_app.repositories.sitzung_repo import SitzungRepository
from qm_app.repositories.thema_repo import ThemaRepository
from qm_app.repositories.besprechung_repo import BesprechungRepository
from qm_app.repositories.verlauf_repo import VerlaufRepository
from qm_app.ui.sitzung_dialog import SitzungDialog
from qm_app.ui.agenda_widget import AgendaDialog


def session(**kwargs):
    return Sitzung(bezeichnung='[AUTOTEST] Sitzung', datum=date(2026,11,21), erstellt_von='ignored', **kwargs)


def test_session_participants_atomic_and_conflict(database):
    repo = SitzungRepository(database)
    participant = SitzungTeilnehmer(sitzung_id=None, person='Fiktive Testperson', rolle='QM')
    id = repo.create(session(beginn=time(9), ende=time(10)), [participant])
    first, people = repo.get(id)
    assert len(people) == 1
    assert first.erstellt_von == database.user
    repo.update(replace(first, status='durchgefuehrt'), [replace(people[0], anwesend=False, vertretung_durch='Testvertretung')])
    current, people2 = repo.get(id)
    assert current.version == first.version + 1
    assert people2[0].id == people[0].id
    assert not people2[0].anwesend
    with pytest.raises(ConcurrencyError):
        repo.update(first, [])
    assert len(repo.get(id)[1]) == 1
    # Failure after the parent UPDATE must roll back its version/status too.
    with pytest.raises(DatabaseError):
        repo.update(replace(current, status='abgesagt'), [replace(people2[0], id=uuid4())])
    assert repo.get(id)[0].version == current.version
    assert repo.get(id)[0].status == 'durchgefuehrt'
    repo.update(current, [])
    assert repo.get(id)[1] == []
    assert len(VerlaufRepository(database).list('qm.sitzung', id)) == 3


def test_agenda_unique_order_decision_deferral_and_conflict(database):
    sessions, topics = SitzungRepository(database), ThemaRepository(database)
    agenda = BesprechungRepository(database)
    id = sessions.create(session())
    target = sessions.create(replace(session(), datum=date(2026,12,1)))
    topic = topics.create(Thema(titel='[AUTOTEST] Tagesordnung', kategorie='Test', erstellt_von='ignored'))
    topic2 = topics.create(Thema(titel='[AUTOTEST] Weiterer TOP', kategorie='Test', erstellt_von='ignored'))
    item = Besprechung(sitzung_id=id, thema_id=topic, top_nr='1', reihenfolge=20, erstellt_von='ignored')
    item_id = agenda.create(item)
    with pytest.raises(DatabaseError, match='bereits vorhanden'):
        agenda.create(item)
    second_id = agenda.create(replace(item, thema_id=topic2, reihenfolge=10))
    assert [row['id'] for row in agenda.list(id)] == [second_id, item_id]
    original = agenda.get(item_id)
    agenda.update(replace(original, status='beschlossen', ergebnis='Beraten', beschluss='Test beschlossen'))
    decided = agenda.get(item_id)
    assert decided.behandelt_am is not None
    assert decided.geaendert_von == database.user
    with pytest.raises(ConcurrencyError):
        agenda.update(original)
    with pytest.raises(DatabaseError):
        agenda.update(replace(decided, status='vertagt', vertagung_nach_sitzung_id=id))
    agenda.update(replace(decided, status='vertagt', vertagung_nach_sitzung_id=target))
    assert agenda.get(item_id).vertagung_nach_sitzung_id == target
    assert agenda.list(target) == []
    events = VerlaufRepository(database).list('qm.besprechung', item_id)
    assert events[0].neue_werte['vertagung_nach_sitzung_id'] == str(target)
    assert len(events) == 3


def test_session_validation():
    with pytest.raises(DatabaseError, match='Ende'):
        SitzungRepository.validate(session(beginn=time(10), ende=time(9)), [])
    person = SitzungTeilnehmer(sitzung_id=None, person='Test')
    with pytest.raises(DatabaseError, match='mehrfach'):
        SitzungRepository.validate(session(), [person, person])


def test_session_dialog_collects_people_and_nullable_times(app, monkeypatch):
    db = MagicMock()
    db.user = 'tester'
    monkeypatch.setattr(QMessageBox, 'warning', MagicMock())
    dialog = SitzungDialog(db)
    dialog.repo = MagicMock()
    dialog.fields['bezeichnung'].setText('Neue Sitzung')
    dialog.add_person()
    dialog.participants.item(0,0).setText('Testperson')
    dialog.participants.item(0,2).setCheckState(Qt.CheckState.Unchecked)
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    saved, people = dialog.repo.create.call_args.args
    assert saved.beginn is None and saved.ende is None
    assert people[0].person == 'Testperson' and not people[0].anwesend
    assert not dialog.agenda.add.isEnabled()
    dialog.close()


def test_session_dialog_conflict(app, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', MagicMock())
    db = MagicMock()
    current = session(id=uuid4())
    dialog = SitzungDialog(db, current)
    dialog.repo = MagicMock()
    dialog.repo.update.side_effect = ConcurrencyError()
    dialog.repo.get.return_value = (replace(current, bezeichnung='Neuer Stand', version=2), [])
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.fields['bezeichnung'].text() == 'Neuer Stand'
    assert dialog.sitzung.version == 2
    dialog.close()


def test_agenda_dialog_real_database(app, database, monkeypatch):
    def fail_on_warning(parent, title, message):
        pytest.fail(f"Unexpected dialog: {title}: {message}")
    monkeypatch.setattr(QMessageBox, "warning", fail_on_warning)
    # Test actual list lookups and real save, still rolled back by the fixture.
    s = SitzungRepository(database).create(session())
    topic = ThemaRepository(database).create(Thema(titel='[AUTOTEST] Dialog', kategorie='Test', erstellt_von='ignored'))
    dialog = AgendaDialog(database, s)
    dialog.thema.setCurrentIndex(dialog.thema.findData(str(topic)))
    dialog.top.setText('3.1')
    dialog.order.setText('3')
    dialog.status.setCurrentText('beschlossen')
    dialog.decision.setPlainText('Testbeschluss')
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    rows = BesprechungRepository(database).list(s)
    assert len(rows) == 1 and rows[0]['beschluss'] == 'Testbeschluss'
    dialog.close()
    target = SitzungRepository(database).create(replace(session(), datum=date(2026,12,1)))
    item = BesprechungRepository(database).get(rows[0]['id'])
    edit = AgendaDialog(database, s, item)
    assert edit.thema.currentData() == str(topic)
    edit.status.setCurrentText('vertagt')
    edit.target.setCurrentIndex(edit.target.findData(str(target)))
    edit.accept()
    assert BesprechungRepository(database).get(item.id).vertagung_nach_sitzung_id == target
    edit.close()
    reopened = AgendaDialog(database, s, BesprechungRepository(database).get(item.id))
    assert reopened.target.currentData() == str(target)
    reopened.close()
