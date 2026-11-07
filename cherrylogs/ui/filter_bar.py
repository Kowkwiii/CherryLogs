"""Search / level / time-range filter bar."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, QTime, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateTimeEdit, QFrame,
                               QHBoxLayout, QLineEdit, QPushButton,
                               QVBoxLayout)

from ..filters import Filters

FMT = "yyyy-MM-dd HH:mm:ss"


def _py(q: QDateTime) -> datetime:
    return q.toPython().replace(tzinfo=None)


def _qdt(dt: datetime) -> QDateTime:
    return QDateTime(QDate(dt.year, dt.month, dt.day),
                     QTime(dt.hour, dt.minute, dt.second))


class FilterBar(QFrame):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        row1 = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search messages and player names\u2026  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.level = QComboBox()
        self.level.addItems(["All", "INFO", "WARN", "ERROR"])
        self.level.setToolTip("Log level")
        self.interactions = QCheckBox("Only events involving every selected player")
        self.reset_btn = QPushButton("Reset filters")
        row1.addWidget(self.search, 1)
        row1.addWidget(self.level)
        row1.addWidget(self.interactions)
        row1.addWidget(self.reset_btn)

        row2 = QHBoxLayout()
        self.from_check = QCheckBox("From")
        self.from_edit = QDateTimeEdit()
        self.to_check = QCheckBox("To")
        self.to_edit = QDateTimeEdit()
        for edit in (self.from_edit, self.to_edit):
            edit.setDisplayFormat(FMT)
            edit.setCalendarPopup(True)
            edit.setEnabled(False)
        row2.addWidget(self.from_check)
        row2.addWidget(self.from_edit)
        row2.addSpacing(10)
        row2.addWidget(self.to_check)
        row2.addWidget(self.to_edit)
        row2.addStretch(1)

        lay.addLayout(row1)
        lay.addLayout(row2)

        self.search.textChanged.connect(self.changed)
        self.level.currentIndexChanged.connect(self.changed)
        self.interactions.toggled.connect(self.changed)
        self.from_check.toggled.connect(self._toggle_from)
        self.to_check.toggled.connect(self._toggle_to)
        self.from_edit.dateTimeChanged.connect(self.changed)
        self.to_edit.dateTimeChanged.connect(self.changed)
        self.reset_btn.clicked.connect(self.reset)

    def _toggle_from(self, on: bool) -> None:
        self.from_edit.setEnabled(on)
        self.changed.emit()

    def _toggle_to(self, on: bool) -> None:
        self.to_edit.setEnabled(on)
        self.changed.emit()

    def set_range(self, first: datetime, last: datetime) -> None:
        """Default values for the date pickers (does not enable them)."""
        for w in (self.from_edit, self.to_edit):
            w.blockSignals(True)
        self.from_edit.setDateTime(_qdt(first))
        self.to_edit.setDateTime(_qdt(last))
        for w in (self.from_edit, self.to_edit):
            w.blockSignals(False)

    def reset(self) -> None:
        for w in (self.search, self.level, self.interactions, self.from_check,
                  self.to_check):
            w.blockSignals(True)
        self.search.clear()
        self.level.setCurrentIndex(0)
        self.interactions.setChecked(False)
        self.from_check.setChecked(False)
        self.to_check.setChecked(False)
        self.from_edit.setEnabled(False)
        self.to_edit.setEnabled(False)
        for w in (self.search, self.level, self.interactions, self.from_check,
                  self.to_check):
            w.blockSignals(False)
        self.changed.emit()

    def filters(self, players: frozenset) -> Filters:
        return Filters(
            players=players,
            interactions_only=self.interactions.isChecked(),
            text=self.search.text().strip(),
            level=self.level.currentText(),
            start=(_py(self.from_edit.dateTime())
                   if self.from_check.isChecked() else None),
            end=(_py(self.to_edit.dateTime())
                 if self.to_check.isChecked() else None),
        )
