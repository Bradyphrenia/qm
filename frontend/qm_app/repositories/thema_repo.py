from uuid import UUID
from qm_app.db import ConcurrencyError, DatabaseError
from qm_app.models import Thema, THEMA_STATUS


class ThemaRepository:
    def __init__(self, database):
        self.db = database

    def list(self):
        with self.db.transaction() as cursor:
            cursor.execute('SELECT * FROM qm.thema ORDER BY erfasst_am DESC, id')
            return [Thema(**row) for row in cursor.fetchall()]

    def get(self, id: UUID):
        with self.db.transaction() as cursor:
            cursor.execute('SELECT * FROM qm.thema WHERE id = %s', (id,))
            row = cursor.fetchone()
            if row is None:
                raise DatabaseError('Das Thema existiert nicht mehr.')
            return Thema(**row)

    @staticmethod
    def validate(thema):
        if not thema.titel.strip() or not thema.kategorie.strip():
            raise DatabaseError('Titel und Kategorie sind Pflichtfelder.')
        if thema.status not in THEMA_STATUS:
            raise DatabaseError('Ungültiger Themenstatus.')
        if len(thema.titel) > 255 or len(thema.kategorie) > 100 or len(thema.prioritaet or '') > 50 or len(thema.epz_fall_id or '') > 100:
            raise DatabaseError('Eine Eingabe ist zu lang.')

    def create(self, thema):
        self.validate(thema)
        if thema.status == 'wiederaufgenommen':
            raise DatabaseError('Neue Themen können nicht als wiederaufgenommen angelegt werden.')
        with self.db.transaction() as cursor:
            cursor.execute('''INSERT INTO qm.thema
                (titel, beschreibung, kategorie, prioritaet, status, verantwortlich, epz_fall_id,
                 erstellt_von, abgeschlossen_am)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s = 'abgeschlossen' THEN CURRENT_TIMESTAMP ELSE NULL END)
                RETURNING id''',
                (thema.titel.strip(), thema.beschreibung, thema.kategorie.strip(), thema.prioritaet,
                 thema.status, thema.verantwortlich, thema.epz_fall_id, self.db.user, thema.status))
            return cursor.fetchone()['id']

    def update(self, thema):
        self.validate(thema)
        with self.db.transaction() as cursor:
            cursor.execute('SELECT status, version FROM qm.thema WHERE id = %s', (thema.id,))
            current = cursor.fetchone()
            if current is None or current['version'] != thema.version:
                raise ConcurrencyError()
            if thema.status == 'wiederaufgenommen' and current['status'] != 'wiederaufgenommen':
                raise DatabaseError('Bitte die Aktion „Wiederaufnehmen“ mit Begründung verwenden.')
            if current['status'] in ('abgeschlossen', 'abgebrochen') and thema.status not in ('abgeschlossen', 'abgebrochen'):
                raise DatabaseError('Bitte das beendete Thema mit Begründung wiederaufnehmen.')
            cursor.execute('''UPDATE qm.thema SET titel = %s, beschreibung = %s,
                kategorie = %s, prioritaet = %s, status = %s, verantwortlich = %s,
                epz_fall_id = %s, geaendert_von = %s,
                abgeschlossen_am = CASE WHEN %s = 'abgeschlossen'
                    THEN COALESCE(abgeschlossen_am, CURRENT_TIMESTAMP) ELSE NULL END
                WHERE id = %s AND version = %s''',
                (thema.titel.strip(), thema.beschreibung, thema.kategorie.strip(), thema.prioritaet,
                 thema.status, thema.verantwortlich, thema.epz_fall_id, self.db.user,
                 thema.status, thema.id, thema.version))
            if cursor.rowcount != 1:
                raise ConcurrencyError()

    def reopen(self, id, version, grund):
        if not grund.strip():
            raise DatabaseError('Eine Begründung für die Wiederaufnahme ist erforderlich.')
        with self.db.transaction() as cursor:
            cursor.execute('''UPDATE qm.thema SET status = 'wiederaufgenommen',
                wiederaufnahme_am = CURRENT_TIMESTAMP, wiederaufnahme_durch = %s,
                wiederaufnahme_grund = %s, abgeschlossen_am = NULL, geaendert_von = %s
                WHERE id = %s AND version = %s''',
                (self.db.user, grund.strip(), self.db.user, id, version))
            if cursor.rowcount != 1:
                raise ConcurrencyError()
