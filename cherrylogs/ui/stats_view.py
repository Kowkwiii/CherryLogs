"""Player statistics tab."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from ..stats import format_duration

HEADERS = ["Player", "Events", "Messages", "Commands", "Joins", "Deaths",
           "Advancements", "Sessions", "Playtime", "First seen", "Last seen",
           "Top command", "IP addresses"]
NUMERIC = {1, 2, 3, 4, 5, 6, 7, 8}


class SortItem(QTableWidgetItem):
    """Table item that sorts by a hidden numeric key instead of its text."""

    def __lt__(self, other) -> bool:
        a = self.data(Qt.ItemDataRole.UserRole)
        b = other.data(Qt.ItemDataRole.UserRole)
        if a is None or b is None:
            return super().__lt__(other)
        return a < b


class Card(QFrame):
    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(0)
        self.value = QLabel("-")
        self.value.setObjectName("CardValue")
        cap = QLabel(label)
        cap.setObjectName("CardLabel")
        lay.addWidget(self.value)
        lay.addWidget(cap)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class StatsView(QWidget):
    investigate = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        row = QHBoxLayout()
        self.cards = {k: Card(k) for k in
                      ("Log entries", "Players", "Chat messages", "Commands",
                       "Time span")}
        for c in self.cards.values():
            row.addWidget(c)
        lay.addLayout(row)

        hint = QLabel("Double-click a player to investigate them. Statistics follow "
                      "the current player and time filters.")
        hint.setObjectName("Muted")
        lay.addWidget(hint)

        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._double_clicked)
        widths = [150, 70, 80, 85, 60, 65, 100, 75, 90, 150, 150, 160, 160]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)
        lay.addWidget(self.table, 1)

    def _double_clicked(self, row: int, _col: int) -> None:
        item = self.table.item(row, 0)
        if item:
            self.investigate.emit(item.text())

    def set_data(self, stats: dict, overview) -> None:
        c = self.cards
        c["Log entries"].set_value(f"{overview.entries:,}")
        c["Players"].set_value(f"{overview.players:,}")
        c["Chat messages"].set_value(f"{overview.messages:,}")
        c["Commands"].set_value(f"{overview.commands:,}")
        if overview.first and overview.last:
            c["Time span"].set_value(
                format_duration((overview.last - overview.first).total_seconds()))
        else:
            c["Time span"].set_value("-")

        t = self.table
        t.setSortingEnabled(False)
        t.setRowCount(len(stats))
        fmt = "%Y-%m-%d %H:%M"
        for r, s in enumerate(sorted(stats.values(), key=lambda s: -s.events)):
            values = [
                (s.name, s.name.lower()), (f"{s.events:,}", s.events),
                (f"{s.messages:,}", s.messages), (f"{s.commands:,}", s.commands),
                (f"{s.joins:,}", s.joins), (f"{s.deaths:,}", s.deaths),
                (f"{s.advancements:,}", s.advancements),
                (f"{len(s.sessions):,}", len(s.sessions)),
                (format_duration(s.playtime), s.playtime),
                (s.first_seen.strftime(fmt) if s.first_seen else "",
                 s.first_seen.timestamp() if s.first_seen else 0),
                (s.last_seen.strftime(fmt) if s.last_seen else "",
                 s.last_seen.timestamp() if s.last_seen else 0),
                (s.top_command, s.top_command),
                (", ".join(sorted(s.ips)), ", ".join(sorted(s.ips))),
            ]
            for col, (text, key) in enumerate(values):
                item = SortItem(text)
                item.setData(Qt.ItemDataRole.UserRole, key)
                if col in NUMERIC or col == 8:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                          Qt.AlignmentFlag.AlignVCenter)
                t.setItem(r, col, item)
        t.setSortingEnabled(True)
        t.sortByColumn(1, Qt.SortOrder.DescendingOrder)
