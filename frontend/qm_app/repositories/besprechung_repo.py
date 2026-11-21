from qm_app.db import ConcurrencyError, DatabaseError
from qm_app.models import Besprechung, BESPRECHUNG_STATUS


class BesprechungRepository:
    def __init__(self, database):
        self.db = database

    def list(self, sitzung_id):
        with self.db.transaction() as cursor:
            cursor.execute('''SELECT b.*, t.titel AS thema_titel FROM qm.besprechung b
                JOIN qm.thema t ON t.id=b.thema_id WHERE b.sitzung_id=%s
                ORDER BY b.reihenfolge NULLS LAST, b.top_nr NULLS LAST, b.id''', (sitzung_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get(self, id):
        with self.db.transaction() as cursor:
            cursor.execute('SELECT * FROM qm.besprechung WHERE id=%s', (id,))
            row = cursor.fetchone()
            if row is None:
                raise DatabaseError('Der Tagesordnungspunkt existiert nicht mehr.')
            return Besprechung(**row)

    @staticmethod
    def validate(item):
        if not item.thema_id:
            raise DatabaseError('Bitte ein Thema auswählen.')
        if item.status not in BESPRECHUNG_STATUS:
            raise DatabaseError('Ungültiger Tagesordnungsstatus.')
        if len(item.top_nr or '') > 50:
            raise DatabaseError('Die TOP-Nummer darf höchstens 50 Zeichen enthalten.')
        if item.vertagung_nach_sitzung_id == item.sitzung_id:
            raise DatabaseError('Bitte eine andere Sitzung als Vertagungsziel wählen.')
        if item.vertagung_nach_sitzung_id and item.status != 'vertagt':
            raise DatabaseError('Eine Folgesitzung ist nur bei Status „vertagt“ zulässig.')

    def create(self, item):
        self.validate(item)
        with self.db.transaction() as cursor:
            cursor.execute('''INSERT INTO qm.besprechung
                (sitzung_id, thema_id, top_nr, reihenfolge, status, ergebnis, beschluss,
                 vertagung_nach_sitzung_id, erstellt_von, behandelt_am)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    CASE WHEN %s IN ('in_beratung','beschlossen') THEN CURRENT_TIMESTAMP ELSE NULL END)
                RETURNING id''', (item.sitzung_id, item.thema_id, item.top_nr, item.reihenfolge,
                item.status, item.ergebnis, item.beschluss, item.vertagung_nach_sitzung_id,
                self.db.user, item.status))
            return cursor.fetchone()['id']

    def update(self, item):
        self.validate(item)
        with self.db.transaction() as cursor:
            cursor.execute('''UPDATE qm.besprechung SET top_nr=%s, reihenfolge=%s,
                status=%s, ergebnis=%s, beschluss=%s, vertagung_nach_sitzung_id=%s,
                geaendert_von=%s, behandelt_am=CASE WHEN %s IN ('in_beratung','beschlossen')
                THEN COALESCE(behandelt_am, CURRENT_TIMESTAMP) ELSE behandelt_am END
                WHERE id=%s AND version=%s AND sitzung_id=%s AND thema_id=%s''',
                (item.top_nr, item.reihenfolge, item.status, item.ergebnis, item.beschluss,
                 item.vertagung_nach_sitzung_id, self.db.user, item.status, item.id,
                 item.version, item.sitzung_id, item.thema_id))
            if cursor.rowcount != 1:
                raise ConcurrencyError()
