import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from qm_app.windows_instance import acquire_application_instance
from qm_app.ui.login_dialog import LoginDialog
from qm_app.ui.main_window import MainWindow


WINDOWS_APP_USER_MODEL_ID = "de.steffentroeger.qm"


def application_icon_path():
    """Return the icon both from source and a PyInstaller one-file bundle."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    base_dir = Path(bundle_dir) if bundle_dir else Path(__file__).resolve().parent
    return base_dir / "qm.ico"


def set_windows_app_user_model_id():
    """Give Windows a stable identity for taskbar grouping and icon lookup."""
    if sys.platform != "win32":
        return
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        WINDOWS_APP_USER_MODEL_ID
    )


def install_german_translation(app):
    """Load Qt's own German texts (Ja/Nein, Abbrechen, Dateidialoge) independent of the OS locale."""
    QLocale.setDefault(QLocale(QLocale.Language.German, QLocale.Country.Germany))
    translator = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale(), "qtbase", "_", path):
        app.installTranslator(translator)
        return True
    return False


def configure_application(app):
    app.setOrganizationName("QM")
    app.setApplicationName("QM Desktop")
    install_german_translation(app)
    icon_path = application_icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))


def main():
    set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    configure_application(app)
    instance = acquire_application_instance()
    if instance is None:
        QMessageBox.information(
            None, "QM ist bereits geöffnet",
            "QM ist bereits geöffnet. Bitte verwende das vorhandene Fenster."
        )
        return 0
    # Closing the login must not terminate the main window's event loop.
    app.setQuitOnLastWindowClosed(False)
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        return 0
    database = login.database
    try:
        window = MainWindow(database)
        window.show()
        app.setQuitOnLastWindowClosed(True)
        return app.exec()
    finally:
        database.close()
        instance.close()


if __name__ == "__main__":
    sys.exit(main())
