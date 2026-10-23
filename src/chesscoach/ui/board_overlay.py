"""Camada transparente sobre o retângulo calibrado. O clique atravessa."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from chesscoach.types import Orientation
from chesscoach.vision.squares import square_to_row_col


class BoardOverlay(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowTitle("Chess Coach setas")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self._arrow: tuple[str, str] | None = None
        self._threats: list[str] = []
        self._orientation = Orientation.WHITE_AT_BOTTOM

    def showEvent(self, event):
        super().showEvent(event)
        _pass_clicks_through(self)

    def set_drawing(
        self,
        orientation: Orientation,
        arrow: tuple[str, str] | None,
        threats: list[str],
    ) -> None:
        self._orientation = orientation
        self._arrow = arrow
        self._threats = list(threats)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for square in self._threats:
            rect = _cell(square, self.width(), self.height(), self._orientation)
            painter.fillRect(rect, QColor(255, 170, 40, 70))
        if self._arrow is not None:
            start = _center(self._arrow[0], self.width(), self.height(), self._orientation)
            end = _center(self._arrow[1], self.width(), self.height(), self._orientation)
            pen = QPen(QColor(80, 200, 255), 4)
            painter.setPen(pen)
            painter.drawLine(start, end)
            painter.setBrush(QColor(80, 200, 255))
            painter.drawEllipse(end, 7, 7)
        painter.end()


def _cell(square: str, width: int, height: int, orientation: Orientation) -> QRectF:
    row, col = square_to_row_col(square, orientation)
    cell_w = width / 8
    cell_h = height / 8
    return QRectF(col * cell_w, row * cell_h, cell_w, cell_h)


def _center(square: str, width: int, height: int, orientation: Orientation) -> QPointF:
    rect = _cell(square, width, height, orientation)
    return rect.center()


def _pass_clicks_through(widget: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00080000 | 0x00000020)
    except (AttributeError, OSError):
        return
