from qm_app.models import Verlauf


class VerlaufRepository:
    def __init__(self, database):
        self.db = database

    def list(self, entitaet, id):
        with self.db.transaction() as cursor:
            cursor.execute('''SELECT * FROM qm.verlauf
                WHERE entitaet = %s AND entitaet_id = %s ORDER BY zeitpunkt DESC, id DESC''',
                (entitaet, str(id)))
            return [Verlauf(**row) for row in cursor.fetchall()]
