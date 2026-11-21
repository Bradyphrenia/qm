from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)


from qm_app.ui.thema_view import ThemaView
from qm_app.ui.sitzung_view import SitzungView


class MainWindow(QMainWindow):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle("QM – Qualitätsmanagement")
        self.resize(1100, 720)
        container = QWidget()
        layout = QHBoxLayout(container)
        self.navigation = QListWidget()
        self.navigation.setMaximumWidth(220)
        self.pages = QStackedWidget()
        for name, step in [("Themen", 2), ("Sitzungen", 3), ("Maßnahmen", 4), ("Dokumente", 5)]:
            self.navigation.addItem(name)
            if name == "Themen":
                self.pages.addWidget(ThemaView(database))
                continue
            if name == "Sitzungen":
                self.pages.addWidget(SitzungView(database))
                continue
            page = QWidget()
            page_layout = QVBoxLayout(page)
            title = QLabel(name)
            font = title.font()
            font.setPointSize(20)
            title.setFont(font)
            page_layout.addWidget(title)
            page_layout.addWidget(QLabel(f"Die {name}verwaltung folgt in Umsetzungsschritt {step}."))
            page_layout.addStretch()
            self.pages.addWidget(page)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        layout.addWidget(self.navigation)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(container)
        self.statusBar().showMessage(f"Angemeldet als {database.user}")
        self.menuBar().addMenu("Datei").addAction("Beenden", self.close)
