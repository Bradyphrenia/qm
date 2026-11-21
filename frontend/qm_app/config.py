from dataclasses import dataclass
from PySide6.QtCore import QSettings


@dataclass(frozen=True)
class ConnectionProfile:
    host: str = "localhost"
    port: int = 5432
    dbname: str = "qm"
    user: str = ""


class Settings:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings("QM", "QM Desktop")

    def load_profile(self):
        s = self.settings
        try:
            port = int(s.value("connection/port", 5432))
        except (TypeError, ValueError):
            port = 5432
        return ConnectionProfile(
            host=str(s.value("connection/host", "localhost")),
            port=port if 1 <= port <= 65535 else 5432,
            dbname=str(s.value("connection/dbname", "qm")),
            user=str(s.value("connection/user", "")),
        )

    def save_profile(self, profile):
        # Only these four fields are persisted; passwords never enter QSettings.
        self.settings.remove("connection/password")
        for key in ("host", "port", "dbname", "user"):
            self.settings.setValue(f"connection/{key}", getattr(profile, key))
        self.settings.sync()
