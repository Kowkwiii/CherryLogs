"""The CherryLogs cherry blossom, drawn with QPainter (no image files needed)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (QBrush, QColor, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap, QRadialGradient)


def _petal_path() -> QPainterPath:
    """A single notched sakura petal pointing up, unit size, origin at base."""
    p = QPainterPath()
    p.moveTo(0, 0)
    p.cubicTo(-0.60, -0.22, -0.66, -0.86, -0.24, -1.00)
    p.quadTo(-0.07, -1.03, 0.0, -0.84)          # left lobe -> notch
    p.quadTo(0.07, -1.03, 0.24, -1.00)          # notch -> right lobe
    p.cubicTo(0.66, -0.86, 0.60, -0.22, 0, 0)
    p.closeSubpath()
    return p


def draw_blossom(painter: QPainter, cx: float, cy: float, radius: float,
                 rotation: float = -90.0 + 18.0) -> None:
    """Paint a five-petal cherry blossom centred at (cx, cy)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(cx, cy)
    petal = _petal_path()

    for i in range(5):
        painter.save()
        painter.rotate(rotation + 90 + i * 72)
        painter.scale(radius, radius)
        grad = QRadialGradient(QPointF(0, 0), 1.0)
        grad.setColorAt(0.00, QColor("#E8608F"))
        grad.setColorAt(0.35, QColor("#F7A3C0"))
        grad.setColorAt(1.00, QColor("#FFE3EC"))
        painter.setBrush(QBrush(grad))
        pen = QPen(QColor("#D9487D"))
        pen.setWidthF(0.035)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(petal)
        # soft vein
        vein = QPen(QColor(217, 72, 125, 110))
        vein.setWidthF(0.02)
        painter.setPen(vein)
        painter.drawLine(QPointF(0, -0.05), QPointF(0, -0.55))
        painter.restore()

    # stamens
    painter.setPen(QPen(QColor("#C2255C"), max(radius * 0.025, 0.6)))
    for i in range(9):
        a = math.radians(i * 40 + 10)
        x, y = math.cos(a) * radius * 0.30, math.sin(a) * radius * 0.30
        painter.drawLine(QPointF(0, 0), QPointF(x, y))
        painter.setBrush(QColor("#FFD43B"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(x, y), radius * 0.045, radius * 0.045)
        painter.setPen(QPen(QColor("#C2255C"), max(radius * 0.025, 0.6)))
    painter.setBrush(QColor("#C2255C"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(0, 0), radius * 0.075, radius * 0.075)
    painter.restore()


def blossom_pixmap(size: int, dpr: float = 1.0) -> QPixmap:
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    draw_blossom(p, size / 2, size / 2 + size * 0.02, size * 0.46)
    p.end()
    return px


def blossom_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(blossom_pixmap(s))
    return icon
