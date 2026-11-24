import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4
import psycopg2
from psycopg2 import sql
from qm_app.db import DatabaseError, ConcurrencyError
from qm_app.models import Dokument, DOKUMENT_STATUS

ENTITIES = {'thema': 'Thema', 'sitzung': 'Sitzung', 'besprechung': 'Tagesordnungspunkt', 'massnahme': 'Maßnahme'}
COLUMNS = ', '.join('d.' + name for name in Dokument.__dataclass_fields__)


@dataclass(frozen=True)
class DocumentSnapshot:
    id: UUID
    version: int
    name: str
    mime_type: str
    checksum: bytes
    data: bytes


class DokumentRepository:
    def __init__(self, database):
        self.db = database

    @staticmethod
    def table(entity):
        if entity not in ENTITIES:
            raise DatabaseError('Ungültige Dokumentzuordnung.')
        return sql.Identifier('qm', entity + '_dokument'), sql.Identifier(entity + '_id')

    def targets(self, entity):
        self.table(entity)
        with self.db.transaction() as c:
            if entity == 'besprechung':
                c.execute('''SELECT b.id, s.bezeichnung || ' / ' || COALESCE(b.top_nr,'TOP') || ' / ' || t.titel AS label
                    FROM qm.besprechung b JOIN qm.sitzung s ON s.id=b.sitzung_id
                    JOIN qm.thema t ON t.id=b.thema_id ORDER BY s.datum DESC,b.reihenfolge''')
            else:
                title = 'bezeichnung' if entity == 'sitzung' else 'titel'
                c.execute(sql.SQL('SELECT id, {} AS label FROM {} ORDER BY {}').format(
                    sql.Identifier(title), sql.Identifier('qm', entity), sql.Identifier(title)))
            return [dict(row) for row in c.fetchall()]

    def list(self, entity=None, entity_id=None):
        with self.db.transaction() as c:
            if entity:
                table, column = self.table(entity)
                c.execute(sql.SQL('SELECT '+COLUMNS+' FROM qm.dokument d JOIN {} l ON l.dokument_id=d.id WHERE l.{}=%s ORDER BY d.erstellt_am DESC,d.id').format(table,column), (entity_id,))
            else:
                c.execute('SELECT '+COLUMNS+' FROM qm.dokument d ORDER BY d.erstellt_am DESC,d.id')
            return [Dokument(**row) for row in c.fetchall()]

    def get(self, id):
        with self.db.transaction() as c:
            c.execute('SELECT '+COLUMNS+' FROM qm.dokument d WHERE d.id=%s', (id,))
            row = c.fetchone()
            if row is None:
                raise DatabaseError('Das Dokument existiert nicht mehr.')
            return Dokument(**row)

    @staticmethod
    def _content(row):
        data = bytes(row['inhalt'])
        checksum = hashlib.sha256(data).digest()
        if len(data) != row['dateigroesse'] or (row['pruefsumme_sha256'] is not None and checksum != bytes(row['pruefsumme_sha256'])):
            raise DatabaseError('Dateigröße oder Prüfsumme stimmt nicht. Download abgebrochen.')
        return data, checksum

    def checkout(self, id, expected_version):
        with self.db.transaction() as c:
            c.execute('''SELECT id,version,dateiname,mime_type,inhalt,dateigroesse,pruefsumme_sha256
                FROM qm.dokument WHERE id=%s FOR SHARE''', (id,))
            row = c.fetchone()
            if row is None or row['version'] != expected_version:
                raise ConcurrencyError()
            data, checksum = self._content(row)
            return DocumentSnapshot(row['id'], row['version'], row['dateiname'], row['mime_type'], checksum, data)

    @staticmethod
    def validate_file(name, mime, data, limit):
        if not name.strip() or len(name) > 255 or not mime or len(mime) > 150:
            raise DatabaseError('Dateiname oder Dateityp ist ungültig.')
        if len(data) > limit:
            raise DatabaseError(f'Die Datei überschreitet das Upload-Limit von {limit // (1024*1024)} MB.')

    def _link(self, c, document_id, entity, entity_id, role=None):
        table, column = self.table(entity)
        if entity_id is None:
            raise DatabaseError('Bitte einen Datensatz für die Zuordnung auswählen.')
        c.execute(sql.SQL('INSERT INTO {} ({},dokument_id,dokument_rolle,erstellt_von) VALUES (%s,%s,%s,%s)').format(table,column),
                  (entity_id,document_id,role,self.db.user))

    def upload(self, name, mime, data, entity, entity_id, dokumenttyp=None, limit=25*1024*1024):
        self.validate_file(name,mime,data,limit)
        if len(dokumenttyp or '') > 100:
            raise DatabaseError('Der Dokumenttyp darf höchstens 100 Zeichen enthalten.')
        id = uuid4()
        with self.db.transaction() as c:
            c.execute('''INSERT INTO qm.dokument (id,dateiname,mime_type,inhalt,dokumenttyp,dokument_gruppe_id,erstellt_von)
                VALUES (%s,%s,%s,%s,%s,%s,%s)''', (id,name,mime,psycopg2.Binary(data),dokumenttyp,id,self.db.user))
            self._link(c,id,entity,entity_id)
        return id

    def link(self, id, entity, entity_id):
        with self.db.transaction() as c:
            self._link(c,id,entity,entity_id)

    def unlink(self, id, entity, entity_id):
        table, column = self.table(entity)
        with self.db.transaction() as c:
            c.execute(sql.SQL('DELETE FROM {} WHERE dokument_id=%s AND {}=%s').format(table,column), (id,entity_id))

    @staticmethod
    def _lock(c, id, expected_version):
        c.execute('SELECT COALESCE(dokument_gruppe_id,id) AS gruppe FROM qm.dokument WHERE id=%s', (id,))
        group = c.fetchone()
        if group is None:
            raise ConcurrencyError()
        # Serialize changes within a version family without schema changes (PG10).
        c.execute("SELECT pg_advisory_xact_lock(hashtext('qm.dokument'),hashtext(%s))", (str(group['gruppe']),))
        c.execute('SELECT '+COLUMNS+' FROM qm.dokument d WHERE d.id=%s FOR UPDATE', (id,))
        row = c.fetchone()
        if row is None or row['version'] != expected_version:
            raise ConcurrencyError()
        return Dokument(**row), group['gruppe']

    def new_version(self, id, expected_version, name, mime, data, limit=25*1024*1024, expected_checksum=None):
        self.validate_file(name,mime,data,limit)
        new_id = uuid4()
        with self.db.transaction() as c:
            old, group = self._lock(c,id,expected_version)
            if expected_checksum is not None:
                if old.pruefsumme_sha256 is not None:
                    current_checksum = bytes(old.pruefsumme_sha256)
                else:
                    c.execute('SELECT inhalt FROM qm.dokument WHERE id=%s', (id,))
                    current_checksum = hashlib.sha256(bytes(c.fetchone()['inhalt'])).digest()
                if current_checksum != bytes(expected_checksum):
                    raise ConcurrencyError()
            c.execute('SELECT id FROM qm.dokument WHERE vorgaenger_dokument_id=%s', (id,))
            if c.fetchone():
                raise DatabaseError('Es gibt bereits eine Nachfolgeversion. Bitte diese auswählen und aktualisieren.')
            predecessor_version = old.version
            if old.status != 'archiviert':
                c.execute('UPDATE qm.dokument SET status=%s,version=version+1 WHERE id=%s AND version=%s',
                          ('archiviert',id,old.version))
                if c.rowcount != 1:
                    raise ConcurrencyError()
                predecessor_version += 1
            c.execute('''INSERT INTO qm.dokument (id,dateiname,mime_type,inhalt,dokumenttyp,version,
                dokument_gruppe_id,vorgaenger_dokument_id,erstellt_von)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (new_id,name,mime,psycopg2.Binary(data),old.dokumenttyp,predecessor_version+1,group,id,self.db.user))
            for entity in ENTITIES:
                table, column = self.table(entity)
                c.execute(sql.SQL('''INSERT INTO {} ({},dokument_id,dokument_rolle,sichtbarkeit,sortierung,erstellt_von)
                    SELECT {},%s,dokument_rolle,sichtbarkeit,sortierung,%s FROM {} WHERE dokument_id=%s''').format(
                    table,column,column,table), (new_id,self.db.user,id))
        return new_id

    def set_status(self, id, expected_version, status):
        if status not in DOKUMENT_STATUS:
            raise DatabaseError('Ungültiger Dokumentstatus.')
        with self.db.transaction() as c:
            old, _ = self._lock(c,id,expected_version)
            if old.status == status:
                return
            c.execute('''UPDATE qm.dokument SET status=%s,version=version+1,
                freigegeben_von=CASE WHEN %s='freigegeben' THEN %s ELSE freigegeben_von END,
                freigegeben_am=CASE WHEN %s='freigegeben' THEN CURRENT_TIMESTAMP ELSE freigegeben_am END
                WHERE id=%s AND version=%s''', (status,status,self.db.user,status,id,expected_version))
            if c.rowcount != 1:
                raise ConcurrencyError()

    def download(self, id):
        with self.db.transaction() as c:
            c.execute('SELECT dateiname,inhalt,dateigroesse,pruefsumme_sha256 FROM qm.dokument WHERE id=%s', (id,))
            row = c.fetchone()
            if row is None:
                raise DatabaseError('Das Dokument existiert nicht mehr.')
            data, _ = self._content(row)
            return row['dateiname'], data

    def delete(self, id, expected_version):
        with self.db.transaction() as c:
            old, _ = self._lock(c,id,expected_version)
            # The database trigger additionally enforces the released-document guard.
            if old.status == 'freigegeben':
                raise DatabaseError('Freigegebene Dokumente dürfen nicht gelöscht werden.')
            c.execute('DELETE FROM qm.dokument WHERE id=%s AND version=%s', (id,expected_version))
            if c.rowcount != 1:
                raise ConcurrencyError()
