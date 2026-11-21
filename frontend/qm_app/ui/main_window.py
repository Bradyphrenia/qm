from datetime import date

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)


from qm_app.ui.thema_view import ThemaView
from qm_app.ui.sitzung_view import SitzungView
from qm_app.ui.massnahme_view import MassnahmeView
from qm_app.ui.dokument_widget import DokumentWidget


class MainWindow(QMainWindow):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle(f"QM – Qualitätsmanagement | © {date.today().year} Steffen Troeger")
        self.resize(1100, 720)
        container = QWidget()
        layout = QHBoxLayout(container)
        self.navigation = QListWidget()
        self.navigation.setMaximumWidth(220)
        self.pages = QStackedWidget()
        for name, view in [("Themen", ThemaView), ("Sitzungen", SitzungView),
                           ("Maßnahmen", MassnahmeView), ("Dokumente", DokumentWidget)]:
            self.navigation.addItem(name)
            self.pages.addWidget(view(database))
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        layout.addWidget(self.navigation)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(container)
        self.statusBar().showMessage(f"Angemeldet als {database.user}")
        self.menuBar().addMenu("Datei").addAction("Beenden", self.close)
