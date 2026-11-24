from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid


class DatabaseError(Exception):
    """User-facing database failure without server details or credentials."""


class ConcurrencyError(DatabaseError):
    def __init__(self):
        super().__init__("Datensatz wurde zwischenzeitlich geändert. Bitte neu laden.")


def translate_error(error):
    messages = {
        "23505": "Diese Zuordnung oder dieser Eintrag ist bereits vorhanden.",
        "23503": "Ein verknüpfter Datensatz fehlt oder wird noch verwendet.",
        "23502": "Bitte alle Pflichtfelder ausfüllen.",
        "23514": "Die Eingaben verletzen eine Datenregel. Bitte Status und Datumsangaben prüfen.",
        "22001": "Eine Eingabe ist zu lang. Bitte den Text kürzen.",
        "42501": "Für diesen Vorgang fehlen die Datenbankberechtigungen.",
        "28P01": "Benutzername oder Passwort ist nicht korrekt.",
        "3D000": "Die angegebene Datenbank existiert nicht.",
        "42P01": "Das erforderliche QM-Schema ist nicht vollständig vorhanden.",
        "P0001": "Die Datenbank hat die Änderung abgewiesen. Freigegebene oder archivierte Dokumentversionen und Verlaufseinträge sind geschützt.",
    }
    if error.pgcode in messages:
        return DatabaseError(messages[error.pgcode])
    if isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError)):
        return DatabaseError("Verbindung fehlgeschlagen oder unterbrochen. Bitte Server, Datenbank und Zugangsdaten prüfen.")
    return DatabaseError("Die Datenbank konnte den Vorgang nicht ausführen.")


class Database:
    def __init__(self, connection, user):
        self.connection = connection
        self.user = user

    @classmethod
    def connect(cls, profile, password):
        connection = None
        try:
            connection = psycopg2.connect(
                host=profile.host, port=profile.port, dbname=profile.dbname,
                user=profile.user, password=password, connect_timeout=5,
                application_name="QM Desktop",
            )
            register_uuid(conn_or_curs=connection)
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_user")
                    user = cursor.fetchone()[0]
                    cursor.execute("SELECT to_regclass('qm.thema')")
                    if cursor.fetchone()[0] is None:
                        raise DatabaseError("Das QM-Schema fehlt in dieser Datenbank.")
            return cls(connection, user)
        except psycopg2.Error as error:
            if connection is not None:
                connection.close()
            raise translate_error(error) from None
        except Exception:
            if connection is not None:
                connection.close()
            raise

    @contextmanager
    def transaction(self):
        """One repository operation; commits on success, rolls back on any failure.

        Do not nest transactions. Pass the cursor to helpers for atomic operations.
        """
        try:
            with self.connection:
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    yield cursor
        except psycopg2.Error as error:
            raise translate_error(error) from None

    def close(self):
        self.connection.close()
