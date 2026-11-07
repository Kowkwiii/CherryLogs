"""Reusable widgets: log table, drag-and-drop overlay, empty state."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QGuiApplication, QKeySequence, QPainter,
                           QPen)
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QLabel, QMenu, QPushButton, QTableView,
                               QVBoxLayout, QWidget)

from ..branding import blossom_pixmap, draw_blossom
from ..theme import LIGHT
from .table_model import EntryTableModel


class EntryTable(QTableView):
    """A table of log entries with copy + 'investigate player' support."""

    investigate = Signal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.entry_model = EntryTableModel(mode, self)
        self.setModel(self.entry_model)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(False)
        self.setShowGrid(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(26)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, col in enumerate(self.entry_model.columns):
            self.setColumnWidth(i, col[2])

    # ---------------------------------------------------------------- copy
    def copy_selection(self) -> None:
        rows = sorted({i.row() for i in self.selectionModel().selectedRows()})
        if rows:
            text = "\n".join(self.entry_model.row_text(r) for r in rows)
            QGuiApplication.clipboard().setText(text)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        idx = self.indexAt(event.pos())
        menu = QMenu(self)
        if idx.isValid():
            entry = self.entry_model.entry_at(idx.row())
            for name in entry.players[:5]:
                act = menu.addAction(f"Investigate {name}")
                act.triggered.connect(lambda _=False, n=name: self.investigate.emit(n))
            if entry.players:
                menu.addSeparator()
        copy = menu.addAction("Copy selected rows")
        copy.triggered.connect(self.copy_selection)
        menu.exec(event.globalPos())


class DropOverlay(QWidget):
    """Translucent 'drop files here' layer shown while dragging."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.pal = LIGHT
        self.hide()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(self.pal["bg"])
        bg.setAlpha(225)
        p.fillRect(self.rect(), bg)
        rect = QRectF(self.rect()).adjusted(18, 18, -18, -18)
        pen = QPen(QColor(self.pal["accent"]), 3, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 22, 22)
        draw_blossom(p, rect.center().x(), rect.center().y() - 30, 54)
        p.setPen(QColor(self.pal["accent"]))
        f = p.font()
        f.setPointSize(17)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(rect.left(), rect.center().y() + 40, rect.width(), 40),
                   Qt.AlignmentFlag.AlignCenter, "Drop your .log or .gz files to import")


class EmptyState(QWidget):
    """Welcome page shown until a log is loaded."""

    browse = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pal = LIGHT
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        logo = QLabel()
        logo.setPixmap(blossom_pixmap(96, self.devicePixelRatioF()))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Drag and drop your Minecraft logs here")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 17pt; font-weight: 600;")
        sub = QLabel("latest.log, debug.log or archived 2024-05-12-1.log.gz files.\n"
                     "CherryLogs splits them into server logs, commands and chat.")
        sub.setObjectName("Muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn = QPushButton("Browse for logs\u2026")
        btn.setObjectName("Primary")
        btn.setMinimumHeight(38)
        btn.clicked.connect(self.browse)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn)
        row.addStretch(1)
        for w in (logo, title, sub):
            lay.addWidget(w)
        lay.addSpacing(8)
        lay.addLayout(row)
        lay.addStretch(2)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(self.pal["border"]), 2, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(14, 14, w - 28, h - 28), 20, 20)
        p.setOpacity(0.28)
        for fx, fy, r, rot in ((0.10, 0.16, 34, 10), (0.90, 0.20, 26, 40),
                               (0.14, 0.82, 22, 70), (0.84, 0.80, 38, 25),
                               (0.50, 0.07, 16, 55), (0.30, 0.92, 15, 5)):
            draw_blossom(p, w * fx, h * fy, r, rot)
