"""Virtual table model: shows hundreds of thousands of rows instantly."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from ..models import CATEGORY_LABELS, EVENT_LABELS
from ..theme import LIGHT, event_color

COLUMN_SETS = {
    "server": [("Time", "ts", 150), ("Level", "level", 70),
               ("Thread", "thread", 170), ("Event", "event", 120),
               ("Players", "players", 140), ("Message", "message", 600)],
    "command": [("Time", "ts", 150), ("Player", "player", 140),
                ("Type", "event", 130), ("Command / feedback", "message", 600)],
    "chat": [("Time", "ts", 150), ("Player", "player", 150),
             ("Message", "message", 700)],
    "all": [("Time", "ts", 150), ("Part", "category", 80),
            ("Event", "event", 130), ("Player", "player", 140),
            ("Details", "message", 600)],
}

LEVEL_COLOR_KEY = {"WARN": "c_warn", "ERROR": "c_error"}


class EntryTableModel(QAbstractTableModel):
    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.columns = COLUMN_SETS[mode]
        self.entries: list = []
        self.pal = LIGHT

    # ---------------------------------------------------------------- data
    def set_entries(self, entries: list) -> None:
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def set_palette(self, pal: dict) -> None:
        self.pal = pal
        if self.entries:
            self.dataChanged.emit(self.index(0, 0),
                                  self.index(len(self.entries) - 1,
                                             len(self.columns) - 1),
                                  [Qt.ItemDataRole.ForegroundRole])

    def entry_at(self, row: int):
        return self.entries[row]

    def _text(self, e, key: str) -> str:
        if key == "ts":
            return e.ts.strftime("%Y-%m-%d %H:%M:%S")
        if key == "event":
            return EVENT_LABELS.get(e.event, e.event)
        if key == "category":
            return CATEGORY_LABELS.get(e.category, e.category)
        if key == "players":
            return ", ".join(e.players)
        if key == "message":
            msg = e.message
            if "\n" in msg:
                msg = msg.split("\n", 1)[0] + "  \u2026"
            return msg
        return getattr(e, key)

    def row_text(self, row: int) -> str:
        e = self.entries[row]
        return "\t".join(self._text(e, c[1]) for c in self.columns)

    # ------------------------------------------------------------- Qt API
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and \
                role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section][0]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        e = self.entries[index.row()]
        key = self.columns[index.column()][1]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(e, key)
        if role == Qt.ItemDataRole.ToolTipRole and key == "message":
            return e.message[:3000]
        if role == Qt.ItemDataRole.ForegroundRole:
            if key in ("event", "category"):
                col = event_color(e.event, self.pal)
                return QColor(col) if col else None
            if key == "level":
                k = LEVEL_COLOR_KEY.get(e.level)
                return QColor(self.pal[k]) if k else None
            if key == "player" and e.player:
                return QColor(self.pal["accent"])
        return None
