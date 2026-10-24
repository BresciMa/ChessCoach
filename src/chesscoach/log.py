"""Log em arquivo. Sem --debug, só erro. Com --debug, o que mudou, não cada quadro."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "chesscoach"


def log_path() -> Path:
    from chesscoach.config import default_config_path

    return default_config_path().parent / "chesscoach.log"


def consume_debug_flag(argv: list[str]) -> tuple[bool, list[str]]:
    return "--debug" in argv, [arg for arg in argv if arg != "--debug"]


def configure(debug: bool, path: Path | None = None) -> Path:
    target = path or log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG if debug else logging.ERROR)
    logger.propagate = False
    handler = RotatingFileHandler(target, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return target


def get(name: str) -> logging.Logger:
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")


class RepeatGate:
    """Segura uma linha igual à anterior até passar o intervalo."""

    def __init__(self, interval_s: float):
        self.interval_s = interval_s
        self._key: str | None = None
        self._at = 0.0

    def allow(self, key: str, now_s: float) -> bool:
        if key == self._key and now_s - self._at < self.interval_s:
            return False
        self._key = key
        self._at = now_s
        return True
