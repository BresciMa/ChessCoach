"""Popup de últimas jogadas. Não entra no layout do chat."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QListWidget

from chesscoach.types import Level


class MovesPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Últimas jogadas")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("movesPopup")
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Últimas jogadas"))
        close = QPushButton("×")
        close.setObjectName("closeMoves")
        close.clicked.connect(self.close)
        header.addWidget(close)
        layout.addLayout(header)
        self.moves = QListWidget()
        self.moves.setObjectName("movesList")
        layout.addWidget(self.moves)
        self.setMinimumWidth(220)

    def show_moves(self, sans: list[str], level: Level, eval_band: str | None, anchor) -> None:
        self.moves.clear()
        lines = format_move_pairs(sans)
        show_band = level in {Level.BEGINNER, Level.LEVEL_1} and eval_band and lines
        for index, line in enumerate(lines):
            if show_band and index == len(lines) - 1:
                line = f"{line}  {eval_band}"
            self.moves.addItem(line)
        self.adjustSize()
        point = anchor.mapToGlobal(anchor.rect().topLeft())
        self.move(point.x() - self.width() - 8, point.y())
        self.show()


def format_move_pairs(sans: list[str]) -> list[str]:
    lines = []
    for index in range(0, len(sans), 2):
        number = index // 2 + 1
        white = sans[index]
        black = sans[index + 1] if index + 1 < len(sans) else ""
        lines.append(f"{number}. {white} {black}".rstrip())
    return lines
