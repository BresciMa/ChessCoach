"""Tipos compartilhados entre captura, visão, coach e interface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class Level(str, Enum):
    BEGINNER = "iniciante_total"
    LEVEL_1 = "nivel_1"
    LEVEL_2 = "nivel_2"
    LEVEL_3 = "nivel_3"
    MASTER = "master"


class Reason(str, Enum):
    MOVE_CONFIRMED = "move_confirmed"
    HINT_REQUESTED = "hint_requested"
    CHAT_MESSAGE = "chat_message"


class Orientation(str, Enum):
    WHITE_AT_BOTTOM = "white_at_bottom"
    BLACK_AT_BOTTOM = "black_at_bottom"


class Theme(str, Enum):
    LICHESS_2D = "lichess_2d"
    CHESSCOM_2D = "chesscom_2d"


class TrackerKind(str, Enum):
    NO_CHANGE = "no_change"
    MOVE_CONFIRMED = "move_confirmed"
    AMBIGUOUS = "ambiguous"
    PROMOTION_NEEDED = "promotion_needed"
    BOARD_UNSTABLE = "board_unstable"
    BOARD_LOST = "board_lost"
    BOARD_CHECK = "board_check"
    READ_REJECTED = "read_rejected"


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


@dataclass
class Frame:
    image: np.ndarray
    time_ms: int


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass
class TrackerResult:
    kind: TrackerKind
    san: str | None = None
    promotion_from: str | None = None
    promotion_to: str | None = None
    message: str | None = None
    restored: bool = False
