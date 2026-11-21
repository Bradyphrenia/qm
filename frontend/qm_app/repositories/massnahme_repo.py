from qm_app.db import DatabaseError, ConcurrencyError
from qm_app.models import Massnahme, MASSNAHME_STATUS, WIRKSAMKEIT_ERGEBNIS


class MassnahmeRepository:
    def __init__(self, database):
        self.db = database

    def list(self, thema_id=None):
        with self.db.transaction() as c:
            c.execute('SELECT * FROM qm.massnahme WHERE (%s::uuid IS NULL OR thema_id=%s) ORDER BY faellig_am NULLS LAST, titel, id', (thema_id, thema_id))
            return [Massnahme(**r) for r in c.fetchall()]

    def get(self, id):
        with self.db.transaction() as c:
            c.execute('SELECT * FROM qm.massnahme WHERE id=%s', (id,))
            r = c.fetchone()
            if r is None:
                raise DatabaseError('Die Maßnahme existiert nicht mehr.')
            return Massnahme(**r)

    @staticmethod
    def validate(m, old=None):
        if not m.thema_id or not m.titel.strip() or not m.verantwortlich.strip():
            raise DatabaseError('Thema, Titel und Verantwortliche sind Pflichtfelder.')
        if len(m.titel) > 255 or len(m.verantwortlich) > 100 or len(m.wirksamkeitspruefung_durch or '') > 100:
            raise DatabaseError('Eine Eingabe ist zu lang.')
        if m.status not in MASSNAHME_STATUS or (m.wirksamkeitspruefung_ergebnis is not None and m.wirksamkeitspruefung_ergebnis not in WIRKSAMKEIT_ERGEBNIS):
            raise DatabaseError('Ungültiger Status oder ungültiges Prüfungsergebnis.')
        needs_reason = m.status in ('abgebrochen', 'zurueckgestellt', 'abgelehnt')
        if old:
            needs_reason |= (old.faellig_am is not None and (m.faellig_am is None or m.faellig_am > old.faellig_am))
            needs_reason |= old.status in ('wirksam', 'abgebrochen', 'abgelehnt') and m.status != old.status
        if needs_reason and not (m.begruendung or '').strip():
            raise DatabaseError('Bitte die Terminverschiebung oder Statusentscheidung begründen.')
        if m.wirksamkeitspruefung_ergebnis and (not m.wirksamkeitspruefung_am or not (m.wirksamkeitspruefung_durch or '').strip()):
            raise DatabaseError('Zur Wirksamkeitsprüfung gehören Datum und prüfende Person.')
        if m.status in ('wirksam', 'nicht_wirksam') and m.wirksamkeitspruefung_ergebnis != m.status:
            raise DatabaseError('Status und Ergebnis der Wirksamkeitsprüfung müssen übereinstimmen.')
        if m.abgeschlossen_am and m.wirksamkeitspruefung_am and m.wirksamkeitspruefung_am < m.abgeschlossen_am:
            raise DatabaseError('Die Wirksamkeitsprüfung darf nicht vor dem Abschluss liegen.')

    @staticmethod
    def values(m):
        return (m.titel.strip(), m.beschreibung, m.ziel, m.verantwortlich.strip(), m.faellig_am,
                m.status, m.abgeschlossen_am, m.wirksamkeitspruefung_ergebnis,
                m.wirksamkeitspruefung_am, m.wirksamkeitspruefung_durch, m.begruendung)

    def create(self, m):
        self.validate(m)
        with self.db.transaction() as c:
            if m.besprechung_id:
                c.execute('SELECT thema_id FROM qm.besprechung WHERE id=%s', (m.besprechung_id,))
                origin = c.fetchone()
                if origin is None or origin['thema_id'] != m.thema_id:
                    raise DatabaseError('Der gewählte TOP gehört nicht zum Thema der Maßnahme.')
            c.execute('''INSERT INTO qm.massnahme
                (titel,beschreibung,ziel,verantwortlich,faellig_am,status,abgeschlossen_am,
                wirksamkeitspruefung_ergebnis,wirksamkeitspruefung_am,wirksamkeitspruefung_durch,
                begruendung,thema_id,besprechung_id,erstellt_von)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                self.values(m)+(m.thema_id,m.besprechung_id,self.db.user))
            return c.fetchone()['id']

    def update(self, m):
        with self.db.transaction() as c:
            c.execute('SELECT * FROM qm.massnahme WHERE id=%s', (m.id,))
            row = c.fetchone()
            if row is None or row['version'] != m.version:
                raise ConcurrencyError()
            old = Massnahme(**row)
            self.validate(m, old)
            if (m.thema_id, m.besprechung_id) != (old.thema_id, old.besprechung_id):
                raise DatabaseError('Thema und Ursprungs-TOP einer bestehenden Maßnahme bleiben unverändert.')
            c.execute('''UPDATE qm.massnahme SET titel=%s,beschreibung=%s,ziel=%s,
                verantwortlich=%s,faellig_am=%s,status=%s,abgeschlossen_am=%s,
                wirksamkeitspruefung_ergebnis=%s,wirksamkeitspruefung_am=%s,
                wirksamkeitspruefung_durch=%s,begruendung=%s,geaendert_von=%s
                WHERE id=%s AND version=%s''', self.values(m)+(self.db.user,m.id,m.version))
            if c.rowcount != 1:
                raise ConcurrencyError()
