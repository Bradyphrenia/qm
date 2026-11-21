"""Repository checks in one rolled-back transaction; never delete audit rows."""
from contextlib import contextmanager
from dataclasses import replace
import os
from uuid import uuid4
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid
import pytest
from qm_app.db import DatabaseError, ConcurrencyError, translate_error
from qm_app.models import Thema
from qm_app.repositories.thema_repo import ThemaRepository
from qm_app.repositories.verlauf_repo import VerlaufRepository




def test_topic_lifecycle_and_audit(database):
    repo = ThemaRepository(database)
    history = VerlaufRepository(database)
    id = repo.create(Thema(titel='[AUTOTEST] ' + str(uuid4()), kategorie='Test', erstellt_von='ignored'))
    original = repo.get(id)
    assert original.erstellt_von == database.user
    assert id in {t.id for t in repo.list()}
    repo.update(replace(original, titel='[AUTOTEST] geändert', status='abgeschlossen'))
    closed = repo.get(id)
    assert closed.version == original.version + 1
    assert closed.abgeschlossen_am is not None
    with pytest.raises(ConcurrencyError):
        repo.update(replace(original, titel='Veralteter Stand'))
    with pytest.raises(DatabaseError):
        repo.update(replace(closed, status='offen'))
    with pytest.raises(DatabaseError):
        repo.reopen(id, closed.version, '  ')
    with pytest.raises(ConcurrencyError):
        repo.reopen(id, original.version, 'Veralteter Stand')
    repo.reopen(id, closed.version, 'Neue Erkenntnisse im Test')
    reopened = repo.get(id)
    assert reopened.version == closed.version + 1
    assert reopened.status == 'wiederaufgenommen'
    assert reopened.abgeschlossen_am is None
    assert reopened.wiederaufnahme_durch == database.user
    assert reopened.geaendert_von == database.user
    events = history.list('qm.thema', id)
    assert len(events) == 3
    assert events[0].neue_werte['wiederaufnahme_grund'] == 'Neue Erkenntnisse im Test'
    assert events[0].alte_werte['status'] == 'abgeschlossen'
    assert events[-1].ereignis_art == 'INSERT'


def test_constraints_and_missing_records(database):
    repo = ThemaRepository(database)
    with pytest.raises(DatabaseError):
        repo.create(Thema(titel=' ', kategorie='Test', erstellt_von='tester'))
    with pytest.raises(DatabaseError):
        repo.create(Thema(titel='Test', kategorie='Test', status='wiederaufgenommen', erstellt_von='tester'))
    with pytest.raises(DatabaseError):
        repo.get(uuid4())
