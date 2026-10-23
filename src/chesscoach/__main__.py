"""Abre a janela do Chess Coach."""

from __future__ import annotations

import os
import sys


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from chesscoach.capture.screen import MonitorCapture
    from chesscoach.coach.session import CoachSession
    from chesscoach.config import default_config_path, load_config
    from chesscoach.engine.uci import StockfishEngine
    from chesscoach.llm.gemini import GeminiProvider
    from chesscoach.ui.coach_window import CoachWindow
    from chesscoach.vision.classifier import TemplateClassifier

    app = QApplication(sys.argv)
    app.setApplicationName("Chess Coach")
    config = load_config()
    session = CoachSession(
        config=config,
        capture=MonitorCapture(),
        classifier=TemplateClassifier(),
        engine=StockfishEngine(config.stockfish_path, config.engine_movetime_ms),
        llm=GeminiProvider(),
        config_path=default_config_path(),
    )
    window = CoachWindow(session)

    def _leave() -> None:
        app.quit()
        os._exit(0)

    window.on_quit = _leave
    window.show()
    app.exec()
    os._exit(0)


if __name__ == "__main__":
    main()
