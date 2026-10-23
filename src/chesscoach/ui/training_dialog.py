"""Aviso de primeiro uso. O texto é o da especificação."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from chesscoach.messages import TRAINING_ACCEPT, TRAINING_DECLINE, TRAINING_TEXT


class TrainingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chess Coach")
        self.setModal(True)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        self.body = QLabel(TRAINING_TEXT)
        self.body.setWordWrap(True)
        self.body.setObjectName("trainingBody")
        layout.addWidget(self.body)
        buttons = QHBoxLayout()
        self.decline_button = QPushButton(TRAINING_DECLINE)
        self.accept_button = QPushButton(TRAINING_ACCEPT)
        self.accept_button.setObjectName("acceptTraining")
        self.decline_button.clicked.connect(self.reject)
        self.accept_button.clicked.connect(self.accept)
        buttons.addWidget(self.decline_button)
        buttons.addWidget(self.accept_button)
        layout.addLayout(buttons)
