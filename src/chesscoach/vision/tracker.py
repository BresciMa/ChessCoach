"""Agendador da captura e tradução de um quadro estável em lance."""

from __future__ import annotations

from enum import Enum

import chess
import numpy as np

from chesscoach.chess.game import ChessGame, affected_squares, match_legal_move
from chesscoach.config import AppConfig
from chesscoach.messages import MSG_AMBIGUOUS, MSG_UNSTABLE
from chesscoach.types import Frame, TrackerKind, TrackerResult
from chesscoach.vision.squares import (
    SQUARE_DIFF_THRESHOLD,
    changed_indices,
    index_to_square,
    signatures_similar,
    square_signature,
)

IDLE_INTERVAL_MS = 250
MOVING_INTERVAL_MS = 100
STABILITY_TIMEOUT_MS = 1000
STABLE_HOLD_MS = 400
MAX_EXTRA_SQUARES = 2
LOST_SQUARE_COUNT = 10


class WatchState(str, Enum):
    IDLE = "idle"
    MOVING = "moving"
    HOLDING = "holding"


class _WatchEvent(str, Enum):
    BASELINE = "baseline"
    NONE = "none"
    STABLE = "stable"
    UNSTABLE = "unstable"


class StabilityWatch:
    """250 ms parado, 100 ms enquanto a peça anda.

    Dois quadros parecidos só começam a contagem. O lance espera cerca de
    400 ms sem nova mudança, para não pegar o arraste no meio.
    """

    def __init__(self, threshold: float = SQUARE_DIFF_THRESHOLD):
        self.threshold = threshold
        self.state = WatchState.IDLE
        self._stable: np.ndarray | None = None
        self._previous: np.ndarray | None = None
        self._moving_since: int | None = None
        self._quiet_since: int | None = None
        self._unstable_latched = False

    def clear(self) -> None:
        self.state = WatchState.IDLE
        self._stable = None
        self._previous = None
        self._moving_since = None
        self._quiet_since = None
        self._unstable_latched = False

    def update(self, signature: np.ndarray, now_ms: int) -> _WatchEvent:
        if self._stable is None:
            self._stable = signature
            self._previous = signature
            self.state = WatchState.IDLE
            return _WatchEvent.BASELINE
        if self.state == WatchState.IDLE:
            if signatures_similar(self._stable, signature, self.threshold):
                self._previous = signature
                self._unstable_latched = False
                return _WatchEvent.NONE
            self._moving_since = now_ms
            self.state = WatchState.MOVING
            self._quiet_since = None
            self._previous = signature
            return _WatchEvent.NONE
        assert self._previous is not None
        if signatures_similar(self._previous, signature, self.threshold):
            return self._hold(signature, now_ms)
        return self._continue_motion(signature, now_ms)

    def _continue_motion(self, signature: np.ndarray, now_ms: int) -> _WatchEvent:
        if self._moving_since is None:
            self._moving_since = now_ms
        self.state = WatchState.MOVING
        self._quiet_since = None
        self._previous = signature
        if now_ms - self._moving_since >= STABILITY_TIMEOUT_MS:
            return self._give_up(signature)
        return _WatchEvent.NONE

    def _hold(self, signature: np.ndarray, now_ms: int) -> _WatchEvent:
        if self._quiet_since is None:
            self.state = WatchState.HOLDING
            self._quiet_since = now_ms
            self._previous = signature
            return _WatchEvent.NONE
        self._previous = signature
        if now_ms - self._quiet_since < STABLE_HOLD_MS:
            self.state = WatchState.HOLDING
            return _WatchEvent.NONE
        self.state = WatchState.IDLE
        self._stable = signature
        self._moving_since = None
        self._quiet_since = None
        self._unstable_latched = False
        return _WatchEvent.STABLE

    def _give_up(self, signature: np.ndarray) -> _WatchEvent:
        self.state = WatchState.IDLE
        self._previous = signature
        self._moving_since = None
        self._quiet_since = None
        if self._unstable_latched:
            return _WatchEvent.NONE
        self._unstable_latched = True
        return _WatchEvent.UNSTABLE


class ScreenCapture:
    def grab(self, monitor: int, region) -> Frame: ...


class PositionTracker:
    def __init__(
        self,
        capture: ScreenCapture,
        game: ChessGame,
        config: AppConfig,
        threshold: float = SQUARE_DIFF_THRESHOLD,
    ):
        self.capture = capture
        self.game = game
        self.config = config
        self.threshold = threshold
        self.watch = StabilityWatch(threshold)
        self._committed: np.ndarray | None = None
        self._last_stable: np.ndarray | None = None
        self._last_poll: int | None = None
        self._pending: tuple[str, str] | None = None
        self._lost = False
        self._occlusion: np.ndarray | None = None
        self.last_image: np.ndarray | None = None

    @property
    def interval_ms(self) -> int:
        if self.watch.state in {WatchState.MOVING, WatchState.HOLDING}:
            return MOVING_INTERVAL_MS
        return IDLE_INTERVAL_MS

    def reset_waiting_for_baseline(self) -> None:
        self.watch.clear()
        self._committed = None
        self._last_stable = None
        self._pending = None
        self._last_poll = None
        self._lost = False
        self._occlusion = None

    def adopt_visual(self) -> None:
        if self._last_stable is not None:
            self._committed = self._last_stable.copy()

    def seed(self, image: np.ndarray) -> None:
        signature = square_signature(image)
        self.watch.clear()
        self.watch.update(signature, 0)
        self._committed = signature
        self._last_stable = signature
        self._pending = None
        self._lost = False
        self._occlusion = None
        self.last_image = image

    def poll(self, now_ms: int) -> TrackerResult | None:
        roi = self.config.roi
        if roi is None:
            return None
        if self._last_poll is not None and now_ms - self._last_poll < self.interval_ms:
            return None
        self._last_poll = now_ms
        frame = self.capture.grab(self.config.monitor, roi)
        return self.ingest(Frame(image=frame.image, time_ms=now_ms))

    def ingest(self, frame: Frame) -> TrackerResult:
        signature = square_signature(frame.image)
        self.last_image = frame.image
        event = self.watch.update(signature, frame.time_ms)
        if event == _WatchEvent.BASELINE:
            self._committed = signature
            self._last_stable = signature
            return TrackerResult(TrackerKind.NO_CHANGE)
        if event == _WatchEvent.NONE:
            return TrackerResult(TrackerKind.NO_CHANGE)
        if event == _WatchEvent.UNSTABLE:
            return TrackerResult(TrackerKind.BOARD_UNSTABLE, message=MSG_UNSTABLE)
        self._last_stable = signature
        if self._lost:
            return self._while_lost(signature)
        result = self._interpret(signature)
        if result.kind == TrackerKind.BOARD_LOST:
            self._lost = True
            self._occlusion = signature.copy()
        return result

    def confirm_promotion(self, piece: str) -> str | None:
        if self._pending is None:
            return None
        origin, destination = self._pending
        move = chess.Move.from_uci(origin + destination + piece)
        if move not in self.game.board.legal_moves:
            return None
        san = self.game.apply(move)
        if self._last_stable is not None:
            self._committed = self._last_stable
        self._pending = None
        return san

    def _while_lost(self, signature: np.ndarray) -> TrackerResult:
        if self._occlusion is not None and signatures_similar(self._occlusion, signature, self.threshold):
            return TrackerResult(TrackerKind.NO_CHANGE)
        if self._committed is not None and signatures_similar(self._committed, signature, self.threshold):
            self._lost = False
            self._occlusion = None
            return TrackerResult(TrackerKind.NO_CHANGE, restored=True)
        self._occlusion = signature.copy()
        return TrackerResult(TrackerKind.BOARD_CHECK)

    def _changed(self, signature: np.ndarray) -> set[str]:
        if self._committed is None:
            return set()
        return {
            index_to_square(index, self.config.orientation)
            for index in changed_indices(self._committed, signature, self.threshold)
        }

    def _interpret(self, signature: np.ndarray) -> TrackerResult:
        if self._committed is None:
            self._committed = signature
            return TrackerResult(TrackerKind.NO_CHANGE)
        changed = self._changed(signature)
        if len(changed) >= LOST_SQUARE_COUNT:
            return TrackerResult(TrackerKind.BOARD_LOST)
        found = match_legal_move(self.game.board, changed)
        if found.kind == TrackerKind.NO_CHANGE:
            if len(changed) > MAX_EXTRA_SQUARES:
                return TrackerResult(TrackerKind.BOARD_CHECK)
            return TrackerResult(TrackerKind.NO_CHANGE)
        if self._extra_squares(changed, found) > MAX_EXTRA_SQUARES:
            return TrackerResult(TrackerKind.BOARD_CHECK)
        if found.kind == TrackerKind.AMBIGUOUS:
            return TrackerResult(TrackerKind.AMBIGUOUS, message=MSG_AMBIGUOUS)
        if found.kind == TrackerKind.PROMOTION_NEEDED:
            self._pending = (found.origin or "", found.destination or "")
            return TrackerResult(
                TrackerKind.PROMOTION_NEEDED,
                promotion_from=found.origin,
                promotion_to=found.destination,
            )
        assert found.move is not None
        san = self.game.apply(found.move)
        self._committed = signature
        return TrackerResult(TrackerKind.MOVE_CONFIRMED, san=san)

    def _extra_squares(self, changed: set[str], found) -> int:
        move = found.move
        if move is None and found.origin and found.destination:
            move = chess.Move.from_uci(found.origin + found.destination)
        if move is None:
            return len(changed)
        return len(changed - affected_squares(self.game.board, move))
