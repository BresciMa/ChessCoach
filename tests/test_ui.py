import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from chesscoach.coach.session import CoachSession
from chesscoach.config import AppConfig
from chesscoach.messages import MSG_BOARD_LOST, MSG_FOLLOWING, TRAINING_ACCEPT, TRAINING_BADGE, TRAINING_TEXT
from chesscoach.types import Level
from chesscoach.ui.board_overlay import BoardOverlay
from chesscoach.ui.coach_window import CoachWindow
from chesscoach.ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


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


class _Silent:
    def analyze(self, fen):
        return None

    def complete(self, messages, model):
        return ""
