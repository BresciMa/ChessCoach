import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from chesscoach.coach.session import CoachSession
from chesscoach.engine.uci import EngineResult
from chesscoach.config import AppConfig
from chesscoach.messages import MSG_BOARD_LOST, MSG_FOLLOWING, TRAINING_ACCEPT, TRAINING_BADGE, TRAINING_TEXT
from chesscoach.types import Level, Reason
from chesscoach.ui.board_overlay import BoardOverlay
from chesscoach.ui.coach_window import CoachWindow
from chesscoach.ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_jose_keeps_a_quiet_line_until_a_reply_is_on_the_way(qapp, caplog):
    import logging

    session = CoachSession(AppConfig(), engine=_Silent(), llm=_Silent())
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    assert window.name_label.text() == "José"
    assert window.avatar.width() == 90
    assert window.avatar.height() == 90
    assert not window._avatar_awake.isNull()
    assert not window._avatar_blind.isNull()
    assert window.thinking_label.text() == ""
    with caplog.at_level(logging.INFO, logger="chesscoach.ui"):
        window._set_thinking(True)
        assert window.thinking_label.text() == "Pensando."
        window._tick_thinking()
        assert window.thinking_label.text() == "Pensando.."
        window._set_thinking(False)
        assert window.thinking_label.text() == ""
        window._set_thinking(True)
        assert window.thinking_label.text() == "Pensando."
    messages = [record.message for record in caplog.records]
    assert messages.count("pensando ligado") == 2
    assert messages.count("pensando desligado") == 1
    window.close()


def test_a_late_phrase_is_dropped_and_thinking_returns_on_the_next_move(qapp, caplog, monkeypatch):
    import logging

    monkeypatch.setattr("chesscoach.coach.orchestrator.api_key_present", lambda: True)
    engine = _Gate()
    session = CoachSession(AppConfig(training_accepted=True, level=Level.LEVEL_1), engine=engine, llm=engine)
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    with caplog.at_level(logging.INFO, logger="chesscoach"):
        session._request_comment(Reason.MOVE_CONFIRMED, None)
        window._start_queued_comment()
        assert window.thinking_label.text() == "Pensando."
        assert engine.entered.wait(2)
        session.game.apply(session.game.parse_san("e4"))
        window._start_queued_comment()
        assert window.thinking_label.text() == ""
        engine.go.set()
        for _ in range(100):
            qapp.processEvents()
            if window._job is None and not engine.busy:
                break
        assert "frase velha" not in window.chat.toPlainText()
        session._request_comment(Reason.MOVE_CONFIRMED, None)
        window._start_queued_comment()
        assert window.thinking_label.text() == "Pensando."
        engine.go.set()
        for _ in range(100):
            qapp.processEvents()
            if "frase nova" in window.chat.toPlainText():
                break
    assert window.thinking_label.text() == ""
    messages = [record.message for record in caplog.records]
    assert "pensando ligado" in messages
    assert "pensando desligado" in messages
    assert "comentario descartado" in messages
    window.close()


def test_dialog_blocks_coach_until_accepted_and_badge_stays(qapp):
    session = CoachSession(AppConfig(), engine=_Silent(), llm=_Silent())
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    assert window.training_dialog.isVisible()
    assert TRAINING_TEXT in window.training_dialog.body.text()
    assert window.input.isEnabled() is False
    assert window.hint_button.isEnabled() is False
    window.training_dialog.accept_button.click()
    qapp.processEvents()
    assert session.config.training_accepted is True
    assert window.training_label.text() == TRAINING_BADGE
    assert window.training_label.isVisible()
    assert window.findChild(type(window.training_label), "hideTrainingLabel") is None
    assert window.windowTitle() == "Chess Coach"
    assert not window.windowFlags() & Qt.WindowType.WindowTransparentForInput
    window.close()


def test_decline_closes_the_window(qapp):
    session = CoachSession(AppConfig(), engine=_Silent(), llm=_Silent())
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    window.training_dialog.decline_button.click()
    qapp.processEvents()
    assert session.config.training_accepted is False
    assert window.isVisible() is False


def test_close_button_hides_the_window(qapp):
    session = CoachSession(AppConfig(training_accepted=True), engine=_Silent(), llm=_Silent())
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    window.close_button.click()
    qapp.processEvents()
    assert window.isVisible() is False


def test_moves_popup_does_not_resize_the_chat(qapp):
    session = CoachSession(AppConfig(training_accepted=True), engine=_Silent(), llm=_Silent())
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    width = window.chat.width()
    height = window.chat.height()
    window._show_moves()
    qapp.processEvents()
    assert window.chat.width() == width
    assert window.chat.height() == height
    assert window.moves_popup.isVisible()
    window.moves_popup.close()
    qapp.processEvents()
    assert window.chat.width() == width
    assert window.chat.height() == height
    window.close()


def test_toolbar_fits_in_56_pixels(qapp):
    session = CoachSession(AppConfig(training_accepted=True), engine=_Silent(), llm=_Silent())
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    assert window.toolbar.width() <= 56
    assert window.hint_button.toolTip() == "Pedir um lance"
    assert window.pause_button.toolTip() == "Pausar"
    window._pause()
    assert window.pause_button.toolTip() == "Retomar"
    window.close()


def test_level_popup_marks_the_current_choice_and_tooltips_stay_available(qapp):
    session = CoachSession(AppConfig(training_accepted=True, level=Level.LEVEL_2), engine=_Silent(), llm=_Silent())
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    assert window.testAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)
    assert window.level_button.toolTip() == "Nível de ajuda: Nível 2"
    window._show_levels()
    qapp.processEvents()
    popup = QApplication.activePopupWidget()
    assert popup is not None
    texts = [button.text() for button in popup.findChildren(QPushButton)]
    assert any(text.startswith("✓") and "Nível 2" in text for text in texts)
    popup.close()
    window.close()


def test_stockfish_path_stays_for_the_next_open(qapp, tmp_path):
    from chesscoach.config import load_config

    path = tmp_path / "config.json"
    config = AppConfig()
    session = CoachSession(config, engine=_Silent(), llm=_Silent(), config_path=path)
    dialog = SettingsDialog(config, on_save=session.save)
    dialog.stockfish.setText(r"C:\Stockfish\stockfish.exe")
    dialog._save()
    reopened = SettingsDialog(load_config(path))
    assert reopened.stockfish.text() == r"C:\Stockfish\stockfish.exe"


def test_settings_lists_gemini_models_and_keeps_a_saved_custom_one(qapp):
    config = AppConfig(gemini_model="gemini-custom")
    dialog = SettingsDialog(config)
    labels = [dialog.model.itemText(index) for index in range(dialog.model.count())]
    assert labels[0] == "gemini-custom"
    assert "gemini-flash-latest" in labels
    assert "gemini-flash-lite-latest" in labels
    assert "gemini-pro-latest" in labels
    assert dialog.model.currentText() == "gemini-custom"
    dialog.model.setCurrentIndex(dialog.model.findData("gemini-pro-latest"))
    dialog._save()
    assert config.gemini_model == "gemini-pro-latest"


def test_chat_marks_user_system_board_and_coach(qapp):
    session = CoachSession(AppConfig(training_accepted=True), engine=_Silent(), llm=_Silent())
    window = CoachWindow(session)
    window.show()
    qapp.processEvents()
    window._append("e o cavalo?", "user")
    window._show(MSG_FOLLOWING)
    window._show(MSG_BOARD_LOST)
    window._append("A posição pede\num lance calmo.", "coach")
    text = window.chat.toPlainText()
    assert "você" in text
    assert "e o cavalo?" in text
    assert "sistema" in text
    assert MSG_FOLLOWING in text
    assert MSG_BOARD_LOST not in text
    assert window.avatar.toolTip() == "O coach ficou cego"
    assert "coach" in text
    assert "A posição pede um lance calmo." in text
    window.close()


def test_overlay_window_lets_clicks_through(qapp):
    overlay = BoardOverlay()
    assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert TRAINING_ACCEPT == "Entendi e aceito"


class _Gate:
    def __init__(self):
        self.entered = threading.Event()
        self.go = threading.Event()
        self.calls = 0
        self.busy = False

    def analyze(self, fen):
        self.calls += 1
        self.busy = True
        self.entered.set()
        self.go.wait(2)
        self.go.clear()
        self.busy = False
        if " b " in fen:
            return EngineResult(10, ["e7e5"])
        return EngineResult(10, ["e2e4"])

    def complete(self, messages, model):
        if self.calls == 1:
            return "frase velha"
        return "frase nova"


class _Silent:
    def analyze(self, fen):
        return None

    def complete(self, messages, model):
        return ""
