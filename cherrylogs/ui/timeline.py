"""Activity timeline: stacked activity chart + per-player session lanes."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QScrollArea,
                               QToolTip, QVBoxLayout, QWidget)

from ..models import CAT_CHAT, CAT_COMMAND
from ..stats import format_duration
from ..theme import LIGHT

BUCKETS = [("Auto", 0), ("1 minute", 60), ("5 minutes", 300),
           ("15 minutes", 900), ("30 minutes", 1800), ("1 hour", 3600),
           ("6 hours", 21600), ("1 day", 86400)]
AUTO_STEPS = [60, 300, 900, 1800, 3600, 10800, 21600, 43200, 86400, 172800]

SERIES = [("Chat", "c_chat"), ("Commands", "c_command"),
          ("Player events", "c_join"), ("Other server", "c_leave")]

LEFT, RIGHT, TOP = 120, 24, 44
CHART_H = 220
LANE_H = 28
MAX_LANES = 15


def _series_index(e) -> int:
    if e.category == CAT_CHAT:
        return 0
    if e.category == CAT_COMMAND:
        return 1
    return 2 if e.players else 3


class TimelineCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pal = LIGHT
        self.setMouseTracking(True)
        self.entries: list = []
        self.markers: list = []
        self.sessions: dict = {}
        self.bucket_choice = 0
        self._hits: list = []
        self._geometry_cache = None
        self.setMinimumHeight(TOP + CHART_H + 60)

    def set_data(self, entries, markers, sessions: dict, bucket_choice: int):
        self.entries = entries
        self.markers = markers
        self.bucket_choice = bucket_choice
        # lanes: most playtime first
        ordered = sorted(sessions.items(),
                         key=lambda kv: -sum(s.seconds for s in kv[1]))
        self.sessions = dict(
            [(n, s) for n, s in ordered if s][:MAX_LANES])
        lanes = len(self.sessions)
        self.setMinimumHeight(TOP + CHART_H + 50 + 70 + max(lanes, 1) * LANE_H)
        self.update()

    def set_palette(self, pal: dict) -> None:
        self.pal = pal
        self.update()

    # ----------------------------------------------------------- painting
    def paintEvent(self, event) -> None:
        pal = self.pal
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(pal["panel"]))
        self._hits = []

        if not self.entries:
            p.setPen(QColor(pal["muted"]))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No activity for the current filters")
            return

        t0 = self.entries[0].ts
        t1 = self.entries[-1].ts
        for lane in self.sessions.values():
            t0 = min(t0, lane[0].start)
            t1 = max(t1, lane[-1].end)
        span = max((t1 - t0).total_seconds(), 60.0)

        plot_w = max(self.width() - LEFT - RIGHT, 50)
        bucket = self.bucket_choice
        if not bucket:
            bucket = next((b for b in AUTO_STEPS if span / b <= 120),
                          AUTO_STEPS[-1])
        n = int(span // bucket) + 1
        counts = [[0, 0, 0, 0] for _ in range(n)]
        for e in self.entries:
            i = int((e.ts - t0).total_seconds() // bucket)
            counts[i][_series_index(e)] += 1
        peak = max(max(sum(c), 1) for c in counts)

        def x_of(t: datetime) -> float:
            return LEFT + (t - t0).total_seconds() / span * plot_w

        # ---- legend
        font = p.font()
        small = QFont(font)
        small.setPointSizeF(font.pointSizeF() - 1)
        p.setFont(small)
        lx = LEFT
        for label, key in SERIES:
            p.setBrush(QColor(pal[key]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(lx, 14, 12, 12), 3, 3)
            p.setPen(QColor(pal["text"]))
            p.drawText(QPointF(lx + 18, 25), label)
            lx += 28 + p.fontMetrics().horizontalAdvance(label)
        p.setPen(QColor(pal["muted"]))
        p.drawText(QPointF(lx + 12, 25), f"bucket: {format_duration(bucket)}")

        # ---- grid + y axis
        plot_top, plot_bot = TOP, TOP + CHART_H
        grid = QPen(QColor(pal["grid"]), 1)
        for i in range(5):
            y = plot_bot - CHART_H * i / 4
            p.setPen(grid)
            p.drawLine(QPointF(LEFT, y), QPointF(LEFT + plot_w, y))
            p.setPen(QColor(pal["muted"]))
            p.drawText(QRectF(0, y - 9, LEFT - 8, 18),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{int(peak * i / 4):,}")

        # ---- bars
        bw = max(plot_w * bucket / span, 1.0)
        for i, c in enumerate(counts):
            total = sum(c)
            if not total:
                continue
            x = LEFT + i * bucket / span * plot_w
            y = plot_bot
            for k, (_, key) in enumerate(SERIES):
                if not c[k]:
                    continue
                h = CHART_H * c[k] / peak
                y -= h
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(pal[key]))
                p.drawRect(QRectF(x, y, max(bw - 1, 1.0), h))
            start = t0.timestamp() + i * bucket
            label = datetime.fromtimestamp(start).strftime("%Y-%m-%d %H:%M")
            tip = f"{label}\n" + "\n".join(
                f"{SERIES[k][0]}: {c[k]:,}" for k in range(4) if c[k])
            self._hits.append((QRectF(x, plot_top, max(bw, 3.0), CHART_H), tip))

        # ---- server start / stop markers
        for m in self.markers:
            if m.ts < t0 or m.ts > t1:
                continue
            x = x_of(m.ts)
            colour = QColor(pal["c_join"] if m.event == "start" else pal["c_death"])
            p.setPen(QPen(colour, 1.5, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, plot_top), QPointF(x, plot_bot))
            self._hits.append((QRectF(x - 3, plot_top, 6, CHART_H),
                               f"{m.ts:%Y-%m-%d %H:%M:%S}\n{m.message[:80]}"))

        # ---- x axis
        p.setPen(QColor(pal["muted"]))
        fmt = "%m-%d" if span > 3 * 86400 else \
              "%m-%d %H:%M" if span > 86400 else "%H:%M"
        ticks = 8
        for i in range(ticks + 1):
            x = LEFT + plot_w * i / ticks
            t = datetime.fromtimestamp(t0.timestamp() + span * i / ticks)
            p.drawLine(QPointF(x, plot_bot), QPointF(x, plot_bot + 4))
            p.drawText(QRectF(x - 45, plot_bot + 6, 90, 18),
                       Qt.AlignmentFlag.AlignHCenter, t.strftime(fmt))

        # ---- player session lanes
        y0 = plot_bot + 50
        p.setFont(font)
        p.setPen(QColor(pal["accent"]))
        bold = QFont(font)
        bold.setBold(True)
        p.setFont(bold)
        p.drawText(QPointF(8, y0), "Player sessions")
        p.setFont(font)
        y0 += 14
        if not self.sessions:
            p.setPen(QColor(pal["muted"]))
            p.drawText(QPointF(LEFT, y0 + 18),
                       "No join/leave events in the current selection.")
        for row, (name, lane) in enumerate(self.sessions.items()):
            y = y0 + row * LANE_H
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal["panel_alt"]))
            p.drawRoundedRect(QRectF(LEFT, y + 4, plot_w, LANE_H - 8), 6, 6)
            p.setPen(QColor(pal["text"]))
            fm = p.fontMetrics()
            p.drawText(QRectF(0, y, LEFT - 10, LANE_H),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(name, Qt.TextElideMode.ElideRight, LEFT - 14))
            for s in lane:
                xa, xb = x_of(s.start), x_of(s.end)
                col = QColor(pal["accent"])
                if not s.clean:
                    col.setAlpha(140)
                rect = QRectF(xa, y + 5, max(xb - xa, 3.0), LANE_H - 10)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(rect, 5, 5)
                note = "" if s.clean else "\n(session end estimated: log/server ended)"
                self._hits.append((rect.adjusted(0, -4, 0, 4),
                                   f"{name}\n{s.start:%Y-%m-%d %H:%M:%S} \u2192 "
                                   f"{s.end:%H:%M:%S}\n{format_duration(s.seconds)}{note}"))

    # -------------------------------------------------------------- hover
    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        for rect, text in reversed(self._hits):
            if rect.contains(pos):
                QToolTip.showText(event.globalPosition().toPoint(), text, self)
                return
        QToolTip.hideText()


class TimelinePanel(QWidget):
    """Timeline tab: bucket-size selector above a scrollable canvas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        top = QHBoxLayout()
        title = QLabel("Activity timeline")
        title.setObjectName("SectionTitle")
        self.bucket = QComboBox()
        for label, secs in BUCKETS:
            self.bucket.addItem(label, secs)
        self.bucket.currentIndexChanged.connect(self._redraw)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(QLabel("Group by"))
        top.addWidget(self.bucket)
        lay.addLayout(top)

        self.canvas = TimelineCanvas()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.canvas)
        lay.addWidget(scroll, 1)
        self._data = ([], [], {})

    def set_data(self, entries, markers, sessions) -> None:
        self._data = (entries, markers, sessions)
        self._redraw()

    def _redraw(self) -> None:
        entries, markers, sessions = self._data
        self.canvas.set_data(entries, markers, sessions,
                             self.bucket.currentData())

    def set_palette(self, pal: dict) -> None:
        self.canvas.set_palette(pal)
