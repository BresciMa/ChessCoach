"""Janela flutuante do coach."""

from __future__ import annotations

import html
import time

import chess
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chesscoach.log import get
from chesscoach.messages import (
    LEVEL_BLURBS,
    LEVEL_LABELS,
    MSG_AMBIGUOUS,
    MSG_BOARD_BACK,
    MSG_BOARD_LOST,
    MSG_ENGINE_SILENT,
    MSG_FOLLOWING,
    MSG_LLM_FAILED,
    MSG_NEED_ROI,
    MSG_NO_ENGINE,
    MSG_NO_KEY,
    MSG_PROMOTION,
    MSG_SSL,
    MSG_UNREADABLE,
    MSG_UNSTABLE,
    TRAINING_BADGE,
)
from chesscoach.types import Level
from chesscoach.ui.board_overlay import BoardOverlay
from chesscoach.ui.calibration import MARK_CODE, CalibrationDialog, pick_rectangle
from chesscoach.ui.moves_popup import MovesPopup
from chesscoach.ui.settings_dialog import SettingsDialog
from chesscoach.ui.training_dialog import TrainingDialog

_STYLE = """
QWidget#coachWindow { background: #141821; color: #e8eef7; font-size: 15px; }
QTextEdit, QLineEdit, QListWidget {
    background: #1c2230; color: #e8eef7; border: 1px solid #2c3548; font-size: 15px;
}
QPushButton#toolButton {
    background: #1c2230; color: #e8eef7; border: none; border-radius: 6px;
    font-size: 16px; min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px;
}
QPushButton#toolButton:disabled { color: #667; }
QLabel#trainingBadge { color: #9ad7ff; }
QLabel#levelLabel { color: #d5deee; }
"""

_BOARD_LINES = {MSG_BOARD_LOST, MSG_BOARD_BACK, MSG_UNSTABLE, MSG_UNREADABLE}
_SILENT_BOARD = {MSG_BOARD_LOST, MSG_BOARD_BACK, MSG_UNSTABLE}
_BLIND_TIP = "O coach ficou cego"
_SYSTEM_LINES = {
    MSG_AMBIGUOUS,
    MSG_ENGINE_SILENT,
    MSG_FOLLOWING,
    MSG_LLM_FAILED,
    MSG_NEED_ROI,
    MSG_NO_ENGINE,
    MSG_NO_KEY,
    MSG_PROMOTION,
    MSG_SSL,
}
_CHAT_KIND = {
    "user": ("#9ad7ff", "você"),
    "system": ("#8b95a8", "sistema"),
    "board": ("#e2b657", "tabuleiro"),
    "coach": ("#d5deee", "coach"),
}


class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._origin: QPoint | None = None
        self._window_origin: QPoint | None = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.globalPosition().toPoint()
            self._window_origin = self.window().pos()

    def mouseMoveEvent(self, event):
        if self._origin is None or self._window_origin is None:
            return
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._origin
            self.window().move(self._window_origin + delta)

    def mouseReleaseEvent(self, event):
        self._origin = None


class CoachWindow(QWidget):
    def __init__(self, session):
        super().__init__(None)
        self.session = session
        self.setObjectName("coachWindow")
        self.setWindowTitle("Chess Coach")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setStyleSheet(_STYLE)
        self.resize(420, 560)
        self._asked = False
        self._drag_guard = False
        self._released = False
        self.on_quit = None

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        column = QVBoxLayout()
        self.title = TitleBar()
        title_row = QHBoxLayout(self.title)
        title_row.setContentsMargins(0, 0, 0, 0)
        self.avatar = QLabel()
        self._avatar_awake = _avatar(28, blind=False)
        self._avatar_blind = _avatar(28, blind=True)
        self.avatar.setPixmap(self._avatar_awake)
        self.avatar.setFixedSize(28, 28)
        self.name_label = QLabel("Chess Coach")
        self.level_label = QLabel(LEVEL_LABELS[session.config.level])
        self.level_label.setObjectName("levelLabel")
        self.training_label = QLabel(TRAINING_BADGE)
        self.training_label.setObjectName("trainingBadge")
        title_row.addWidget(self.avatar)
        title_row.addWidget(self.name_label)
        title_row.addWidget(self.level_label)
        title_row.addWidget(self.training_label)
        title_row.addStretch(1)
        minimize = QPushButton("–")
        minimize.setObjectName("toolButton")
        minimize.setToolTip("Minimizar")
        minimize.clicked.connect(self.showMinimized)
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("toolButton")
        self.close_button.setToolTip("Fechar")
        self.close_button.clicked.connect(self._quit_application)
        title_row.addWidget(minimize)
        title_row.addWidget(self.close_button)
        column.addWidget(self.title)

        self.chat = QTextEdit()
        self.chat.setObjectName("chatLog")
        self.chat.setReadOnly(True)
        self.chat.document().setDocumentMargin(4)
        self.chat.document().setDefaultStyleSheet("p { margin-top: 1px; margin-bottom: 1px; }")
        column.addWidget(self.chat, 1)
        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Pergunte ao coach...")
        self.input.returnPressed.connect(self._send)
        self.send_button = QPushButton("Enviar")
        self.send_button.clicked.connect(self._send)
        input_row.addWidget(self.input)
        input_row.addWidget(self.send_button)
        column.addLayout(input_row)
        root.addLayout(column, 1)

        self.toolbar = QWidget()
        self.toolbar.setObjectName("toolbar")
        self.toolbar.setFixedWidth(52)
        tools = QVBoxLayout(self.toolbar)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(6)
        self.pause_button = self._tool("❚❚", "Pausar", self._pause)
        self.hint_button = self._tool("💡", "Pedir um lance", self._hint)
        self.arrows_button = self._tool("↗", "Mostrar setas no tabuleiro", self._arrows)
        self.calibrate_button = self._tool("⌖", "Marcar o tabuleiro", self._calibrate)
        self.moves_button = self._tool("≡", "Últimas jogadas", self._show_moves)
        self.level_button = self._tool("★", "Nível de ajuda", self._show_levels)
        self._refresh_level_tip()
        self.settings_button = self._tool("⚙", "Configurações", self._settings)
        for button in (
            self.pause_button,
            self.hint_button,
            self.arrows_button,
            self.calibrate_button,
            self.moves_button,
            self.level_button,
            self.settings_button,
        ):
            tools.addWidget(button)
        tools.addStretch(1)
        root.addWidget(self.toolbar)

        self.moves_popup = MovesPopup(self)
        self.training_dialog = TrainingDialog(self)
        self.training_dialog.accepted.connect(self._on_training_accepted)
        self.training_dialog.rejected.connect(self._on_training_rejected)
        self.overlay = BoardOverlay()
        self._set_coach_enabled(session.config.training_accepted)

        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._asked and not self.session.config.training_accepted:
            self._asked = True
            self.training_dialog.open()

    def closeEvent(self, event):
        self._release()
        event.accept()
        self._finish_process()

    def _on_training_rejected(self) -> None:
        if self._released:
            return
        QTimer.singleShot(0, self._quit_application)

    def _quit_application(self) -> None:
        self._release()
        if self.isVisible():
            self.close()
        self._finish_process()

    def _release(self) -> None:
        if self._released:
            return
        self._released = True
        get("ui").info("janela encerrada")
        self.timer.stop()
        self.overlay.hide()
        self.training_dialog.setModal(False)
        self.training_dialog.hide()
        try:
            self.overlay.close()
        except RuntimeError:
            pass
        try:
            self.session.save()
        except Exception:
            pass

    def _finish_process(self) -> None:
        hook = self.on_quit
        self.on_quit = None
        if hook is not None:
            hook()

    def _tool(self, text: str, tip: str, slot) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("toolButton")
        button.setToolTip(tip)
        button.setFixedSize(44, 44)
        button.clicked.connect(slot)
        return button

    def _set_coach_enabled(self, enabled: bool) -> None:
        self.input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.hint_button.setEnabled(enabled)
        self.arrows_button.setEnabled(enabled)

    def _on_training_accepted(self) -> None:
        self.session.accept_training()
        self._set_coach_enabled(True)
        self.training_label.setText(TRAINING_BADGE)

    def _append(self, text: str, kind: str = "coach") -> None:
        color, label = _CHAT_KIND[kind]
        body = html.escape(" ".join(text.split()))
        self.chat.append(
            f'<p style="margin:1px 0; line-height:1.2">'
            f'<span style="color:{color}; font-size:11px">{label}</span> '
            f'<span style="color:#e8eef7">{body}</span></p>'
        )

    def _set_blind(self, blind: bool) -> None:
        self.avatar.setPixmap(self._avatar_blind if blind else self._avatar_awake)
        self.avatar.setToolTip(_BLIND_TIP if blind else "")

    def _show(self, text: str) -> None:
        if text in _SILENT_BOARD:
            self._set_blind(text != MSG_BOARD_BACK)
            return
        if text in _BOARD_LINES:
            kind = "board"
        elif text in _SYSTEM_LINES:
            kind = "system"
        else:
            kind = "coach"
        self._append(text, kind)

    def _send(self) -> None:
        if not self.session.config.training_accepted:
            return
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._append(text, "user")
        reply = self.session.send_chat(text)
        if reply:
            self._show(reply)
        self._sync_overlay()

    def _hint(self) -> None:
        if not self.session.config.training_accepted:
            return
        reply = self.session.request_hint()
        if reply:
            self._show(reply)
        self._sync_overlay()

    def _pause(self) -> None:
        paused = self.session.toggle_pause()
        self.pause_button.setToolTip("Retomar" if paused else "Pausar")
        self.pause_button.setText("▶" if paused else "❚❚")
        self._sync_overlay()

    def _arrows(self) -> None:
        if not self.session.config.training_accepted:
            return
        self.session.toggle_arrows()
        self._sync_overlay()

    def _show_moves(self) -> None:
        self.moves_popup.show_moves(
            self.session.game.sans,
            self.session.config.level,
            self.session.last_eval_band,
            self.moves_button,
        )

    def _show_levels(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        dialog.setStyleSheet(_STYLE)
        layout = QVBoxLayout(dialog)
        current = self.session.config.level
        for level in Level:
            mark = "✓ " if level == current else ""
            button = QPushButton(f"{mark}{LEVEL_LABELS[level]} — {LEVEL_BLURBS[level]}")
            if level == current:
                button.setStyleSheet("font-weight: 700;")
            button.clicked.connect(lambda _checked=False, value=level, popup=dialog: self._choose_level(value, popup))
            layout.addWidget(button)
        dialog.move(self.level_button.mapToGlobal(self.level_button.rect().topLeft()))
        dialog.show()

    def _choose_level(self, level: Level, dialog: QDialog) -> None:
        self.session.set_level(level)
        self.level_label.setText(LEVEL_LABELS[level])
        self._refresh_level_tip()
        dialog.close()

    def _refresh_level_tip(self) -> None:
        self.level_button.setToolTip(f"Nível de ajuda: {LEVEL_LABELS[self.session.config.level]}")

    def _settings(self) -> None:
        dialog = SettingsDialog(self.session.config, self, on_save=self.session.save)
        if dialog.exec():
            self.session.save()

    def _calibrate(self) -> None:
        dialog = CalibrationDialog(self)
        screens = QApplication.screens()
        for index, screen in enumerate(screens):
            dialog.monitor.addItem(screen.name() or f"Monitor {index + 1}", index)
        if self.session.config.monitor < dialog.monitor.count():
            dialog.monitor.setCurrentIndex(self.session.config.monitor)
        while True:
            code = dialog.exec()
            if code != MARK_CODE:
                break
            index = max(0, dialog.monitor.currentIndex())
            if not screens:
                break
            rect = self._pick_rectangle(screens[min(index, len(screens) - 1)])
            if rect is not None:
                dialog.rect_value = rect
                dialog.status.setText(f"Retângulo {rect.width}×{rect.height}.")
        if code not in (1, 2):
            return
        monitor = dialog.monitor.currentData()
        if monitor is None:
            monitor = dialog.monitor.currentIndex()
        error = self.session.set_calibration(
            int(monitor),
            dialog.rect_value,
            dialog.orientation.currentData(),
        )
        if error:
            self._show(error)
            return
        if not self.session.config.training_accepted:
            self.training_dialog.open()
            return
        if code == 1:
            message = self.session.follow_from_start()
        else:
            frame = self.session.capture.grab(self.session.config.monitor, self.session.config.roi)
            message = self.session.read_now(frame, dialog.side.currentData())
        self._set_blind(self.session.blind)
        if message:
            self._show(message)

    def _pick_rectangle(self, screen):
        self.timer.stop()
        self.overlay.hide()
        self.hide()
        try:
            return pick_rectangle(screen)
        finally:
            self.show()
            self.raise_()
            self.activateWindow()
            self.timer.start()

    def _on_timer(self) -> None:
        now = int(time.monotonic() * 1000)
        start = len(self.session.messages)
        lines = self.session.poll(now)
        self._set_blind(self.session.blind)
        for line in lines:
            self._show(line)
        if MSG_PROMOTION in lines:
            self._ask_promotion(start)
        self._sync_overlay()

    def _ask_promotion(self, start: int) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Promoção")
        layout = QHBoxLayout(dialog)
        chosen = {"piece": "q"}

        def pick(piece: str) -> None:
            chosen["piece"] = piece
            dialog.accept()

        for label, piece in (("Dama", "q"), ("Torre", "r"), ("Bispo", "b"), ("Cavalo", "n")):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, value=piece: pick(value))
            layout.addWidget(button)
        dialog.exec()
        self.session.confirm_promotion(chosen["piece"])
        for line in self.session.messages[start:]:
            if line != MSG_PROMOTION and line not in self.chat.toPlainText():
                self._show(line)

    def _sync_overlay(self) -> None:
        state = self.session.overlay_state()
        roi = self.session.config.roi
        screens = QApplication.screens()
        if not state.visible or roi is None or not screens:
            self.overlay.hide()
            return
        screen = screens[min(self.session.config.monitor, len(screens) - 1)]
        origin = screen.geometry()
        self.overlay.setGeometry(origin.x() + roi.x, origin.y() + roi.y, roi.width, roi.height)
        self.overlay.set_drawing(
            self.session.config.orientation,
            _arrow_squares(self.session, state.arrow),
            state.threat_squares,
        )
        self.overlay.show()


def _arrow_squares(session, san: str | None) -> tuple[str, str] | None:
    if not san:
        return None
    try:
        move = session.game.board.parse_san(san)
    except ValueError:
        return None
    return chess.square_name(move.from_square), chess.square_name(move.to_square)


def _avatar(size: int, blind: bool = False) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor("#8b95a8") if blind else QColor("#3dbeff"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size - 1, size - 1)
    if not blind:
        painter.setBrush(QColor("#102033"))
        painter.drawEllipse(size // 5, size // 4, size // 6, size // 6)
        painter.drawEllipse(size * 3 // 5, size // 4, size // 6, size // 6)
    painter.end()
    return pixmap
