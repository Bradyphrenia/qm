from dataclasses import dataclass
from datetime import date, datetime, time
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


@dataclass(frozen=True)
class Column:
    key: str
    title: str


class TableModel(QAbstractTableModel):
    SortRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, columns, rows=(), parent=None):
        super().__init__(parent)
        self.columns = tuple(columns)
        self.rows = list(rows)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)) or not (0 <= index.column() < len(self.columns)):
            return None
        row = self.rows[index.row()]
        key = self.columns[index.column()].key
        value = row.get(key) if isinstance(row, dict) else getattr(row, key)
        if role == self.SortRole:
            return value.isoformat() if isinstance(value, (date, datetime, time)) else value
        if role == Qt.ItemDataRole.DisplayRole:
            if value is None:
                return ""
            if isinstance(value, datetime):
                return value.astimezone().strftime("%d.%m.%Y %H:%M")
            if isinstance(value, date):
                return value.strftime("%d.%m.%Y")
            if isinstance(value, bool):
                return "Ja" if value else "Nein"
            return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.columns):
            return self.columns[section].title
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()
