"""Configurações. A chave da API não tem campo."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from chesscoach.config import DEFAULT_GEMINI_MODEL, GEMINI_MODELS
from chesscoach.messages import KEY_HELP, TRAINING_TEXT


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.config = config
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.monitor = QSpinBox()
        self.monitor.setRange(0, 7)
        self.monitor.setValue(config.monitor)
        self.stockfish = QLineEdit(config.stockfish_path)
        browse = QPushButton("Procurar")
        browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.stockfish)
        path_row.addWidget(browse)
        self.model = QComboBox()
        saved = config.gemini_model or DEFAULT_GEMINI_MODEL
        names = list(GEMINI_MODELS)
        if saved not in names:
            names.insert(0, saved)
        for name in names:
            self.model.addItem(name, name)
        self.model.setCurrentIndex(max(0, self.model.findData(saved)))
        form.addRow("Monitor", self.monitor)
        form.addRow("Stockfish", path_row)
        form.addRow("Modelo Gemini", self.model)
        layout.addLayout(form)
        help_label = QLabel(KEY_HELP)
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        notice = QLabel(TRAINING_TEXT)
        notice.setWordWrap(True)
        layout.addWidget(notice)
        save = QPushButton("Guardar")
        save.clicked.connect(self._save)
        layout.addWidget(save)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Stockfish", "", "Executável (*.exe);;Todos (*)")
        if path:
            self.stockfish.setText(path)

    def _save(self) -> None:
        self.config.monitor = self.monitor.value()
        self.config.stockfish_path = self.stockfish.text().strip()
        chosen = self.model.currentData()
        self.config.gemini_model = chosen or DEFAULT_GEMINI_MODEL
        self.accept()
