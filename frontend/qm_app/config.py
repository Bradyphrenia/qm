from dataclasses import dataclass, field
import sys

from PySide6.QtCore import QSettings


WINDOWS_DATABASE_HOST = "139.64.201.9"
DATABASE_NAME = "qm"


def default_database_host(platform=None):
    platform = sys.platform if platform is None else platform
    return "localhost" if platform == "darwin" else WINDOWS_DATABASE_HOST


@dataclass(frozen=True)
class ConnectionProfile:
    host: str = field(default_factory=default_database_host)
    port: int = 5432
    dbname: str = DATABASE_NAME
    user: str = "qm"


class Settings:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings("QM", "QM Desktop")

    def load_profile(self):
        s = self.settings
        default_host = default_database_host()
        dbname = str(s.value("connection/dbname", DATABASE_NAME))
        if dbname in {"epz", "epz.qm"}:
            dbname = DATABASE_NAME
        try:
            port = int(s.value("connection/port", 5432))
        except (TypeError, ValueError):
            port = 5432
        return ConnectionProfile(
            host=str(s.value("connection/host", default_host)),
            port=port if 1 <= port <= 65535 else 5432,
            dbname=dbname,
            user=str(s.value("connection/user", "qm")),
        )

    def save_profile(self, profile):
        # Only these four fields are persisted; passwords never enter QSettings.
        self.settings.remove("connection/password")
        for key in ("host", "port", "dbname", "user"):
            self.settings.setValue(f"connection/{key}", getattr(profile, key))
        self.settings.sync()

    def upload_limit_mb(self):
        try:
            value = int(self.settings.value('documents/upload_limit_mb', 25))
        except (ValueError, TypeError):
            return 25
        return value if 1 <= value <= 1024 else 25

    def save_upload_limit(self, megabytes):
        if not 1 <= megabytes <= 1024:
            raise ValueError('Upload-Limit muss zwischen 1 und 1024 MB liegen.')
        self.settings.setValue('documents/upload_limit_mb', megabytes)
        self.settings.sync()
