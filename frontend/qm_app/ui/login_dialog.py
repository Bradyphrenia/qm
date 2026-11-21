from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QMessageBox, QSpinBox,
)
from qm_app.config import ConnectionProfile, Settings
from qm_app.db import Database, DatabaseError


class LoginDialog(QDialog):
    def __init__(self, parent=None, settings=None, connect=None):
        super().__init__(parent)
        self.setWindowTitle("QM – Datenbank anmelden")
        self.settings = settings if settings is not None else Settings()
        self.connect = connect if connect is not None else Database.connect
        self.database = None
        profile = self.settings.load_profile()
        self.host = QLineEdit(profile.host)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(profile.port)
        self.dbname = QLineEdit(profile.dbname)
        self.user = QLineEdit(profile.user)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout = QFormLayout(self)
        for label, field in [("Host", self.host), ("Port", self.port), ("Datenbank", self.dbname), ("Benutzer", self.user), ("Passwort", self.password)]:
            layout.addRow(label, field)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Verbinden")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def accept(self):
        profile = ConnectionProfile(self.host.text().strip(), self.port.value(), self.dbname.text().strip(), self.user.text().strip())
        if not all((profile.host, profile.dbname, profile.user)):
            QMessageBox.warning(self, "Anmeldung", "Bitte Host, Datenbank und Benutzer angeben.")
            return
        self.buttons.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        error_message = None
        try:
            self.database = self.connect(profile, self.password.text())
        except DatabaseError as error:
            error_message = str(error)
        finally:
            QApplication.restoreOverrideCursor()
            self.buttons.setEnabled(True)
        if error_message:
            QMessageBox.warning(self, "Verbindung fehlgeschlagen", error_message)
            return
        self.settings.save_profile(profile)
        self.password.clear()
        super().accept()

    def reject(self):
        self.password.clear()
        super().reject()
