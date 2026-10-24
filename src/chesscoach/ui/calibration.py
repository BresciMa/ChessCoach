"""Marcação do retângulo e escolha de tema, orientação e modo."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEventLoop, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chesscoach.messages import CALIBRATION_HELP, MSG_NEED_ROI
from chesscoach.types import Orientation, Rect

MARK_CODE = 3


class RubberBand(QWidget):
    selected = Signal(object)
    closed = Signal()

    def __init__(self, screen):
        super().__init__(None)
        self._ratio = float(screen.devicePixelRatio() or 1)
        self._origin = None
        self._current = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setGeometry(screen.geometry())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._hint = QLabel("Arraste sobre as 64 casas. Esc cancela.", self)
        self._hint.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 200); padding: 8px; font-size: 16px;"
        )
        self._hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._hint.move(24, 24)
        self._hint.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus()
        _force_topmost_and_clickable(self)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._origin = event.position().toPoint()
        self._current = self._origin
        self.update()

    def mouseMoveEvent(self, event):
        if self._origin is None:
            return
        self._current = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        if self._origin is None:
            return
        self._current = event.position().toPoint()
        rect = _physical(_normalized(self._origin, self._current), self._ratio)
        if rect.width >= 64 and rect.height >= 64:
            self.selected.emit(rect)
            self.close()
            return
        self._hint.setText("Arraste uma área maior, só sobre as 64 casas. Esc cancela.")
        self._hint.adjustSize()
        self._origin = None
        self._current = None
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        if self._origin is not None and self._current is not None:
            rect = _normalized(self._origin, self._current)
            painter.setPen(QPen(QColor(80, 200, 255), 3))
            painter.drawRect(rect.x, rect.y, rect.width, rect.height)
        painter.end()


def pick_rectangle(screen) -> Rect | None:
    band = RubberBand(screen)
    chosen: dict[str, Rect] = {}
    loop = QEventLoop()
    band.selected.connect(lambda rect: chosen.setdefault("rect", rect))
    band.closed.connect(loop.quit)
    band.show()
    loop.exec()
    band.deleteLater()
    return chosen.get("rect")


class CalibrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Marcar o tabuleiro")
        self.rect_value: Rect | None = None
        layout = QVBoxLayout(self)
        help_label = QLabel(CALIBRATION_HELP)
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.monitor = QComboBox()
        self.orientation = QComboBox()
        self.orientation.addItem("Eu jogo de Brancas embaixo", Orientation.WHITE_AT_BOTTOM)
        self.orientation.addItem("Eu jogo de Pretas embaixo", Orientation.BLACK_AT_BOTTOM)
        self.side = QComboBox()
        self.side.addItem("Jogam as Brancas", "w")
        self.side.addItem("Jogam as Pretas", "b")
        for label, widget in (
            ("Monitor", self.monitor),
            ("Orientação", self.orientation),
            ("Quem joga agora", self.side),
        ):
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
        self.status = QLabel(MSG_NEED_ROI)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        mark = QPushButton("Marcar retângulo")
        mark.clicked.connect(self._mark)
        layout.addWidget(mark)
        row = QHBoxLayout()
        self.follow_button = QPushButton("Acompanhar do início")
        self.read_button = QPushButton("Ler posição agora")
        self.follow_button.clicked.connect(self._follow)
        self.read_button.clicked.connect(self._read)
        row.addWidget(self.follow_button)
        row.addWidget(self.read_button)
        layout.addLayout(row)

    def show_saved(self, orientation, side: str) -> None:
        orientation_index = self.orientation.findData(orientation)
        if orientation_index < 0:
            orientation_index = self.orientation.findData(getattr(orientation, "value", orientation))
        if orientation_index >= 0:
            self.orientation.setCurrentIndex(orientation_index)
        side_index = self.side.findData(side)
        if side_index >= 0:
            self.side.setCurrentIndex(side_index)

    def _mark(self) -> None:
        self.done(MARK_CODE)

    def _follow(self) -> None:
        self.done(1)

    def _read(self) -> None:
        self.done(2)


def _normalized(origin, current) -> Rect:
    x0, y0 = origin.x(), origin.y()
    x1, y1 = current.x(), current.y()
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    return Rect(left, top, max(0, right - left), max(0, bottom - top))


def _physical(rect: Rect, ratio: float) -> Rect:
    return Rect(
        int(round(rect.x * ratio)),
        int(round(rect.y * ratio)),
        int(round(rect.width * ratio)),
        int(round(rect.height * ratio)),
    )


def _force_topmost_and_clickable(widget: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, (style | 0x00080000) & ~0x00000020)
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)
    except (AttributeError, OSError):
        return
