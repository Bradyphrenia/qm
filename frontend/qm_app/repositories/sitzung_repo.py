from qm_app.db import ConcurrencyError, DatabaseError
from qm_app.models import Sitzung, SitzungTeilnehmer, SITZUNG_STATUS


class SitzungRepository:
    def __init__(self, database):
        self.db = database

    def list(self):
        with self.db.transaction() as cursor:
            cursor.execute('SELECT * FROM qm.sitzung ORDER BY datum DESC, bezeichnung, id')
            return [Sitzung(**row) for row in cursor.fetchall()]

    def get(self, id):
        # Load parent and children from a consistent snapshot. Participant writes
        # through this repository always lock/update the parent first.
        with self.db.transaction() as cursor:
            cursor.execute('SELECT * FROM qm.sitzung WHERE id = %s FOR SHARE', (id,))
            row = cursor.fetchone()
            if row is None:
                raise DatabaseError('Die Sitzung existiert nicht mehr.')
            cursor.execute('SELECT * FROM qm.sitzung_teilnehmer WHERE sitzung_id = %s ORDER BY person, id', (id,))
            return Sitzung(**row), [SitzungTeilnehmer(**p) for p in cursor.fetchall()]

    @staticmethod
    def validate(sitzung, participants):
        if not sitzung.bezeichnung.strip():
            raise DatabaseError('Bitte eine Bezeichnung für die Sitzung eingeben.')
        if sitzung.status not in SITZUNG_STATUS:
            raise DatabaseError('Ungültiger Sitzungsstatus.')
        if sitzung.beginn and sitzung.ende and sitzung.ende < sitzung.beginn:
            raise DatabaseError('Das Ende darf nicht vor dem Beginn liegen.')
        for field, limit in [('bezeichnung', 255), ('sitzungsart', 100), ('ort', 255), ('leitung', 100), ('protokollfuehrung', 100)]:
            if len(getattr(sitzung, field) or '') > limit:
                raise DatabaseError('Eine Sitzungseingabe ist zu lang.')
        names = set()
        for p in participants:
            if not p.person.strip():
                raise DatabaseError('Bitte für alle Teilnehmenden einen Namen eingeben.')
            if p.person.strip() in names:
                raise DatabaseError('Eine Person ist mehrfach als teilnehmend eingetragen.')
            names.add(p.person.strip())
            if any(len(getattr(p, f) or '') > 100 for f in ('person', 'rolle', 'vertretung_durch')):
                raise DatabaseError('Name, Rolle und Vertretung dürfen höchstens 100 Zeichen enthalten.')

    @staticmethod
    def values(s):
        return (s.bezeichnung.strip(), s.datum, s.beginn, s.ende, s.sitzungsart,
                s.ort, s.leitung, s.protokollfuehrung, s.status)

    def create(self, sitzung, participants=()):
        self.validate(sitzung, participants)
        with self.db.transaction() as cursor:
            cursor.execute('''INSERT INTO qm.sitzung
                (bezeichnung, datum, beginn, ende, sitzungsart, ort, leitung, protokollfuehrung, status, erstellt_von)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                self.values(sitzung) + (self.db.user,))
            id = cursor.fetchone()['id']
            self.save_participants(cursor, id, participants)
            return id

    def update(self, sitzung, participants):
        self.validate(sitzung, participants)
        with self.db.transaction() as cursor:
            cursor.execute('''UPDATE qm.sitzung SET bezeichnung=%s, datum=%s, beginn=%s,
                ende=%s, sitzungsart=%s, ort=%s, leitung=%s, protokollfuehrung=%s,
                status=%s, geaendert_von=%s WHERE id=%s AND version=%s''',
                self.values(sitzung) + (self.db.user, sitzung.id, sitzung.version))
            if cursor.rowcount != 1:
                raise ConcurrencyError()
            self.save_participants(cursor, sitzung.id, participants)

    @staticmethod
    def save_participants(cursor, id, participants):
        # Participants have no version column; the parent version protects the batch.
        # Preserve existing UUIDs, also when renaming a participant.
        cursor.execute('SELECT id FROM qm.sitzung_teilnehmer WHERE sitzung_id=%s', (id,))
        existing = {row['id'] for row in cursor.fetchall()}
        if any(p.id is not None and p.id not in existing for p in participants):
            raise DatabaseError('Ein Teilnehmendeneintrag gehört nicht zu dieser Sitzung.')
        cursor.execute('DELETE FROM qm.sitzung_teilnehmer WHERE sitzung_id=%s', (id,))
        for p in participants:
            cursor.execute('''INSERT INTO qm.sitzung_teilnehmer
                (id, sitzung_id, person, rolle, anwesend, vertretung_durch, bemerkung)
                VALUES (COALESCE(%s, qm.gen_random_uuid()), %s, %s, %s, %s, %s, %s)''',
                (p.id, id, p.person.strip(), p.rolle, p.anwesend, p.vertretung_durch, p.bemerkung))
