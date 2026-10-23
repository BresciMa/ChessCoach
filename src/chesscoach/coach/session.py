"""Liga tracker, analisador, política e as duas janelas. Não cria funcionalidade fora da spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import chess

from chesscoach.analysis.analyzer import PositionAnalyzer
from chesscoach.analysis.facts import CoachFacts
from chesscoach.capture.screen import MonitorCapture
from chesscoach.chess.game import ChessGame, shortest_replays
from chesscoach.coach.orchestrator import CoachOrchestrator, chat_reason
from chesscoach.coach.policy import PolicyDecision, StockHelpPolicy
from chesscoach.config import AppConfig, save_config
from chesscoach.engine.uci import ChessEngine, StockfishEngine
from chesscoach.llm.provider import LlmProvider
from chesscoach.messages import (
    MSG_AMBIGUOUS,
    MSG_BOARD_BACK,
    MSG_BOARD_LOST,
    MSG_FOLLOWING,
    MSG_NEED_ROI,
    MSG_PROMOTION,
    MSG_UNREADABLE,
    MSG_UNSTABLE,
)
from chesscoach.types import Frame, Level, Orientation, Reason, Theme, TrackerKind
from chesscoach.vision.classifier import PieceClassifier, TemplateClassifier
from chesscoach.vision.roi import CalibrationError, RoiCalibrator
from chesscoach.vision.tracker import PositionTracker


@dataclass
class OverlayState:
    visible: bool
    arrow: str | None
    threat_squares: list[str] = field(default_factory=list)
    paused: bool = False


class CoachSession:
    def __init__(
        self,
        config: AppConfig,
        capture: MonitorCapture | None = None,
        classifier: PieceClassifier | None = None,
        engine: ChessEngine | None = None,
        llm: LlmProvider | None = None,
        config_path: Path | None = None,
    ):
        self.config = config
        self.config_path = config_path
        self.capture = capture if capture is not None else MonitorCapture()
        self.classifier = classifier if classifier is not None else TemplateClassifier()
        self.engine = engine if engine is not None else StockfishEngine(
            config.stockfish_path, config.engine_movetime_ms
        )
        self.game = ChessGame()
        self.tracker = PositionTracker(self.capture, self.game, config)
        self.analyzer = PositionAnalyzer()
        self.policy = StockHelpPolicy()
        self.orchestrator = CoachOrchestrator(
            self.policy,
            llm if llm is not None else _UnavailableLlm(),
            config.gemini_model,
        )
        self.paused = False
        self.messages: list[str] = []
        self._awaiting_move_text = False
        self._previous_cp: int | None = None
        self._last_facts: CoachFacts | None = None
        self._last_decision: PolicyDecision | None = None
        self.last_eval_band: str | None = None
        self._arrow: str | None = None
        self._threats: list[str] = []
        self._pending_promotion = False
        self._board_lost = False
        self.blind = False
        self._last_look: int | None = None
        self.calibrator = RoiCalibrator()

    def save(self) -> None:
        if isinstance(self.engine, StockfishEngine):
            self.engine.path = self.config.stockfish_path
            self.engine.movetime_ms = self.config.engine_movetime_ms
        self.orchestrator.model = self.config.gemini_model
        if self.config_path is not None:
            save_config(self.config, self.config_path)

    def accept_training(self) -> None:
        self.config.training_accepted = True
        self.save()

    def set_level(self, level: Level) -> None:
        self.config.level = level
        self.save()

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        if self.paused:
            self._arrow = None
            self._threats = []
        return self.paused

    def toggle_arrows(self) -> bool:
        if not self.config.training_accepted:
            return False
        self.config.arrows_enabled = not self.config.arrows_enabled
        if self.config.arrows_enabled and self._last_decision is not None:
            self._apply_decision(self._last_decision)
        else:
            self._arrow = None
            self._threats = []
        self.save()
        return self.config.arrows_enabled

    def set_calibration(self, monitor: int, rect, orientation, theme=None) -> str | None:
        orientation = Orientation(orientation)
        if theme is None:
            theme = self.config.theme
        theme = Theme(theme)
        try:
            self.calibrator.set(monitor, rect, orientation, theme)
        except CalibrationError as exc:
            return str(exc)
        self.config.monitor = monitor
        self.config.roi = rect
        self.config.orientation = orientation
        self.config.theme = theme
        self.save()
        return None

    def follow_from_start(self) -> str | None:
        if self.config.roi is None:
            return MSG_NEED_ROI
        if not self.config.training_accepted:
            return None
        self.game.reset()
        self.tracker.reset_waiting_for_baseline()
        self._previous_cp = None
        self._last_facts = None
        self._arrow = None
        self._threats = []
        self.blind = False
        self._board_lost = False
        self._say(MSG_FOLLOWING)
        return None

    def read_now(self, frame: Frame, side_to_move: str = "w") -> str | None:
        if self.config.roi is None:
            return MSG_NEED_ROI
        if not self.config.training_accepted:
            return None
        before = self.game.fen
        found = self.classifier.read_board(frame, self.config.orientation, self.config.theme, side_to_move)
        if not found.ok or not found.fen:
            if self.game.fen != before:
                self.game.load_fen(before, self.game.history_known)
            return MSG_UNREADABLE
        self.game.load_fen(found.fen, history_known=False)
        self.tracker.seed(frame.image)
        self._previous_cp = None
        self._last_facts = None
        self.blind = False
        self._board_lost = False
        return None

    def confirm_promotion(self, piece: str) -> None:
        san = self.tracker.confirm_promotion(piece)
        self._pending_promotion = False
        if san and self._user_to_move():
            self._comment(Reason.MOVE_CONFIRMED, None)

    def poll(self, now_ms: int) -> list[str]:
        start = len(self.messages)
        if not self.config.training_accepted or self.paused or self.config.roi is None:
            return []
        if self._pending_promotion:
            return []
        try:
            result = self.tracker.poll(now_ms)
        except Exception:
            self._say(MSG_UNREADABLE)
            return self.messages[start:]
        if result is None:
            return self.messages[start:]
        if result.restored:
            self.blind = False
            self._note_board_back()
        if result.kind == TrackerKind.NO_CHANGE:
            if self.blind:
                self._look_again(now_ms)
            return self.messages[start:]
        if result.kind == TrackerKind.BOARD_UNSTABLE:
            self.blind = True
            self._say(MSG_UNSTABLE)
        elif result.kind == TrackerKind.BOARD_LOST:
            self.blind = True
            if not self._board_lost:
                self._board_lost = True
                self._say(MSG_BOARD_LOST)
        elif result.kind == TrackerKind.BOARD_CHECK:
            self._reconnect(now_ms)
        elif result.kind == TrackerKind.AMBIGUOUS:
            self._awaiting_move_text = True
            self._say(MSG_AMBIGUOUS)
        elif result.kind == TrackerKind.PROMOTION_NEEDED:
            self._pending_promotion = True
            self._say(MSG_PROMOTION)
        elif result.kind == TrackerKind.MOVE_CONFIRMED:
            self._arrow = None
            self._threats = []
            if self._user_to_move():
                self._comment(Reason.MOVE_CONFIRMED, None)
        return self.messages[start:]

    def request_hint(self) -> str | None:
        if not self.config.training_accepted:
            return None
        self._comment(Reason.HINT_REQUESTED, None)
        return self.messages[-1] if self.messages else None

    def send_chat(self, text: str) -> str | None:
        if not self.config.training_accepted:
            return None
        cleaned = text.strip()
        if not cleaned:
            return None
        if self._awaiting_move_text:
            move = self.game.parse_san(cleaned)
            if move is not None:
                self.game.apply(move)
                self.tracker.adopt_visual()
                self._awaiting_move_text = False
                self._comment(Reason.MOVE_CONFIRMED, None)
                return self.messages[-1] if self.messages else None
        self._comment(chat_reason(cleaned), cleaned)
        return self.messages[-1] if self.messages else None

    def overlay_state(self) -> OverlayState:
        if self.paused or not self.config.arrows_enabled or self.config.roi is None:
            return OverlayState(False, None, [], paused=self.paused)
        return OverlayState(True, self._arrow, list(self._threats), paused=False)

    def _comment(self, reason: Reason, user_text: str | None) -> None:
        if isinstance(self.engine, StockfishEngine):
            self.engine.path = self.config.stockfish_path
            self.engine.movetime_ms = self.config.engine_movetime_ms
        self.orchestrator.model = self.config.gemini_model
        result = self.engine.analyze(self.game.fen)
        facts = self.analyzer.analyze(self.game, result, self._previous_cp)
        if result is not None:
            self._previous_cp = result.evaluation_cp
        self._last_facts = facts
        turn = self.orchestrator.respond(facts, self.config.level, reason, user_text)
        self._last_decision = turn.decision
        self.last_eval_band = turn.decision.eval_band
        self._apply_decision(turn.decision)
        if turn.text:
            self._say(turn.text)

    def _apply_decision(self, decision: PolicyDecision) -> None:
        if self.paused or not self.config.arrows_enabled:
            self._arrow = None
            self._threats = []
            return
        self._arrow = decision.arrow
        self._threats = list(decision.threat_squares)

    def _user_to_move(self) -> bool:
        user_white = self.config.orientation == Orientation.WHITE_AT_BOTTOM
        return self.game.board.turn == (chess.WHITE if user_white else chess.BLACK)

    def _note_board_back(self) -> None:
        self._board_lost = False
        self._say(MSG_BOARD_BACK)

    def _look_again(self, now_ms: int) -> None:
        """Enquanto cego, a imagem parada ainda pode ser o tabuleiro que já conhecíamos."""
        if self.tracker.matches_committed():
            self.blind = False
            self._board_lost = False
            return
        if not self.tracker.is_settled() or self.tracker.current_is_flat():
            return
        if self._last_look is not None and now_ms - self._last_look < _LOOK_AGAIN_MS:
            return
        self._reconnect(now_ms)

    def _reconnect(self, now_ms: int | None = None) -> None:
        if now_ms is not None:
            self._last_look = now_ms
        image = self.tracker.last_image
        if image is None:
            return
        lost = self._board_lost
        before = self.game.fen
        known = self.game.history_known
        side = "w" if self.game.board.turn == chess.WHITE else "b"
        found = self.classifier.read_board(
            Frame(image=image, time_ms=0),
            self.config.orientation,
            self.config.theme,
            side,
        )
        if not found.ok or not found.fen:
            if self.game.fen != before:
                self.game.load_fen(before, known)
            if _mean_confidence(found) < _LOST_MEAN_CONFIDENCE:
                self.blind = True
                if not self._board_lost:
                    self._board_lost = True
                    self._say(MSG_BOARD_LOST)
            return
        placement = {item.square: item.piece for item in found.squares if item.piece}
        paths = shortest_replays(self.game.board, placement)
        same_pieces = paths == [[]]
        if len(paths) == 1:
            for move in paths[0]:
                self.game.apply(move)
        else:
            fen = found.fen
            if paths:
                probe = self.game.board.copy()
                for move in paths[0]:
                    probe.push(move)
                fen = _fen_with_turn(found.fen, probe.turn)
            self.game.load_fen(fen, history_known=False)
        self.tracker.seed(image)
        self._previous_cp = None
        self._last_facts = None
        self.blind = False
        if lost:
            self._note_board_back()
            return
        if not same_pieces and self._user_to_move():
            self._comment(Reason.MOVE_CONFIRMED, None)

    def _say(self, text: str) -> None:
        self.messages.append(text)


_LOST_MEAN_CONFIDENCE = 0.35
_LOOK_AGAIN_MS = 1000


def _mean_confidence(found) -> float:
    if not found.squares:
        return 0.0
    return sum(item.confidence for item in found.squares) / len(found.squares)


def _fen_with_turn(fen: str, turn: chess.Color) -> str:
    parts = fen.split(" ")
    if len(parts) < 2:
        return fen
    parts[1] = "w" if turn == chess.WHITE else "b"
    return " ".join(parts)


class _UnavailableLlm:
    def complete(self, messages, model: str) -> str:
        raise RuntimeError("Provedor ausente.")
