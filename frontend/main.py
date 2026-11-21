import sys
from PySide6.QtWidgets import QApplication, QDialog
from qm_app.ui.login_dialog import LoginDialog
from qm_app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("QM")
    app.setApplicationName("QM Desktop")
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


if __name__ == "__main__":
    sys.exit(main())
