"""Configuração do usuário. A chave da API não entra neste arquivo."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from chesscoach.types import Level, Orientation, Rect, Theme

GEMINI_MODELS = (
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
)
DEFAULT_GEMINI_MODEL = GEMINI_MODELS[0]
_SECRET_KEYS = {"gemini_api_key", "GEMINI_API_KEY", "api_key", "apiKey"}


@dataclass
class AppConfig:
    training_accepted: bool = False
    level: Level = Level.BEGINNER
    monitor: int = 0
    roi: Rect | None = None
    orientation: Orientation = Orientation.WHITE_AT_BOTTOM
    theme: Theme = Theme.LICHESS_2D
    stockfish_path: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL
    engine_movetime_ms: int = 300
    arrows_enabled: bool = False

    def to_dict(self) -> dict:
        payload = {
            "training_accepted": self.training_accepted,
            "level": _enum_value(self.level),
            "monitor": self.monitor,
            "roi": None
            if self.roi is None
            else {
                "x": self.roi.x,
                "y": self.roi.y,
                "width": self.roi.width,
                "height": self.roi.height,
            },
            "orientation": _enum_value(self.orientation),
            "theme": _enum_value(self.theme),
            "stockfish_path": self.stockfish_path,
            "gemini_model": self.gemini_model,
            "engine_movetime_ms": self.engine_movetime_ms,
            "arrows_enabled": self.arrows_enabled,
        }
        return {key: value for key, value in payload.items() if key not in _SECRET_KEYS}

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        clean = {key: value for key, value in data.items() if key not in _SECRET_KEYS}
        roi_raw = clean.get("roi")
        roi = None
        if isinstance(roi_raw, dict):
            roi = Rect(
                int(roi_raw["x"]),
                int(roi_raw["y"]),
                int(roi_raw["width"]),
                int(roi_raw["height"]),
            )
        level = _enum(Level, clean.get("level"), Level.BEGINNER)
        orientation = _enum(Orientation, clean.get("orientation"), Orientation.WHITE_AT_BOTTOM)
        theme = _enum(Theme, clean.get("theme"), Theme.LICHESS_2D)
        return cls(
            training_accepted=bool(clean.get("training_accepted", False)),
            level=level,
            monitor=int(clean.get("monitor", 0)),
            roi=roi,
            orientation=orientation,
            theme=theme,
            stockfish_path=str(clean.get("stockfish_path", "")),
            gemini_model=str(clean.get("gemini_model") or DEFAULT_GEMINI_MODEL),
            engine_movetime_ms=int(clean.get("engine_movetime_ms", 300)),
            arrows_enabled=bool(clean.get("arrows_enabled", False)),
        )


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / ".config"
    return root / "ChessCoach" / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    target = path or default_config_path()
    if not target.is_file():
        return AppConfig()
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return AppConfig()
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = config.to_dict()
    if _SECRET_KEYS & payload.keys():
        raise RuntimeError("A configuração não pode guardar a chave da API.")
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _enum_value(value) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _enum(kind, value, fallback):
    try:
        return kind(value)
    except ValueError:
        return fallback
