"""Liga tracker, analisador, política e as duas janelas. Não cria funcionalidade fora da spec."""

from __future__ import annotations

import time
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
from chesscoach.log import RepeatGate, get
from chesscoach.messages import (
    MSG_AMBIGUOUS,
    MSG_BOARD_BACK,
    MSG_BOARD_LOST,
    MSG_ENGINE_SILENT,
    MSG_FOLLOWING,
    MSG_NEED_ROI,
    MSG_NO_ENGINE,
    MSG_PROMOTION,
    MSG_UNREADABLE,
    MSG_UNSTABLE,
)
from chesscoach.types import Frame, Level, Orientation, Reason, Theme, TrackerKind
from chesscoach.vision.classifier import PieceClassifier, TemplateClassifier
from chesscoach.vision.roi import CalibrationError, RoiCalibrator
from chesscoach.vision.square_model import MIN_CONFIDENCE
from chesscoach.vision.tracker import PositionTracker

_LOG = get("session")


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
        self._read_gate = RepeatGate(5.0)
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
        _LOG.info("treino aceito")

    def set_level(self, level: Level) -> None:
        self.config.level = level
        self.save()
        _LOG.info("nivel %s", level.value)

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        _LOG.info("pausa %s", "sim" if self.paused else "nao")
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
        _LOG.info("setas %s", "sim" if self.config.arrows_enabled else "nao")
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
        _LOG.info("calibracao monitor=%s retangulo=%s orientacao=%s", monitor, rect, orientation.value)
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
        self._mark_blind(False)
        self._board_lost = False
        self._say(MSG_FOLLOWING)
        _LOG.info("acompanhar do inicio")
        return None

    def read_now(self, frame: Frame, side_to_move: str = "w") -> str | None:
        if self.config.roi is None:
            return MSG_NEED_ROI
        if not self.config.training_accepted:
            return None
        before = self.game.fen
        found = self.classifier.read_board(frame, self.config.orientation, self.config.theme, side_to_move)
        self._log_read("agora", found)
        if not found.ok or not found.fen:
            if self.game.fen != before:
                self.game.load_fen(before, self.game.history_known)
            return MSG_UNREADABLE
        self.game.load_fen(found.fen, history_known=False)
        self.tracker.seed(frame.image)
        self._previous_cp = None
        self._last_facts = None
        self._mark_blind(False)
        self._board_lost = False
        _LOG.info("ler agora fen=%s", found.fen)
        return None

    def confirm_promotion(self, piece: str) -> None:
        _LOG.info("promocao %s", piece)
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
            _LOG.exception("falha ao observar o quadro")
            self._say(MSG_UNREADABLE)
            return self.messages[start:]
        if result is None:
            return self.messages[start:]
        if result.restored:
            self._mark_blind(False)
            self._note_board_back()
        if result.kind == TrackerKind.NO_CHANGE:
            if self.blind:
                self._look_again(now_ms)
            return self.messages[start:]
        if result.kind == TrackerKind.BOARD_UNSTABLE:
            self._mark_blind(True)
            self._say(MSG_UNSTABLE)
        elif result.kind == TrackerKind.BOARD_LOST:
            self._mark_blind(True)
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
        _LOG.info("dica pedida")
        self._comment(Reason.HINT_REQUESTED, None)
        return self.messages[-1] if self.messages else None

    def send_chat(self, text: str) -> str | None:
        if not self.config.training_accepted:
            return None
        cleaned = text.strip()
        if not cleaned:
            return None
        _LOG.info("usuario %s", cleaned[:180])
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
        engine_started = time.perf_counter()
        result = self.engine.analyze(self.game.fen)
        engine_ms = int((time.perf_counter() - engine_started) * 1000)
        facts = self.analyzer.analyze(self.game, result, self._previous_cp)
        if result is not None:
            self._previous_cp = result.evaluation_cp
        self._last_facts = facts
        turn = self.orchestrator.respond(facts, self.config.level, reason, user_text)
        if turn.text == MSG_NO_ENGINE and self.config.stockfish_path:
            turn.text = MSG_ENGINE_SILENT
        self._last_decision = turn.decision
        self.last_eval_band = turn.decision.eval_band
        self._apply_decision(turn.decision)
        _LOG.info(
            "coach motivo=%s motor=%s motor_ms=%s llm_ms=%s fen=%s",
            reason.value,
            "sim" if result is not None else "nao",
            engine_ms,
            "-" if turn.llm_ms is None else turn.llm_ms,
            self.game.board.fen(),
        )
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
            self._mark_blind(False)
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
        self._log_read("acompanhamento", found)
        if not found.ok or not found.fen:
            if self.game.fen != before:
                self.game.load_fen(before, known)
            if _mean_confidence(found) < _LOST_MEAN_CONFIDENCE:
                self._mark_blind(True)
                if not self._board_lost:
                    self._board_lost = True
                    self._say(MSG_BOARD_LOST)
            return
        placement = {item.square: item.piece for item in found.squares if item.piece}
        paths = shortest_replays(self.game.board, placement)
        same_pieces = paths == [[]]
        piece_diff = _piece_diff_count(self.game.board, placement)
        if not paths and piece_diff <= 3:
            _LOG.info("leitura ignorada pecas=%s sem sequencia legal", piece_diff)
            return
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
        self._mark_blind(False)
        if lost:
            self._note_board_back()
            return
        if not same_pieces and self._user_to_move():
            self._comment(Reason.MOVE_CONFIRMED, None)

    def _mark_blind(self, blind: bool) -> None:
        if self.blind == blind:
            return
        self.blind = blind
        _LOG.info("avatar %s", "cego" if blind else "enxergando")

    def _log_read(self, purpose: str, found) -> None:
        low = sorted(
            (item for item in found.squares if item.confidence < MIN_CONFIDENCE),
            key=lambda item: item.confidence,
        )
        worst = ", ".join(f"{item.square}:{item.confidence:.2f}" for item in low[:4]) or "-"
        text = "leitura %s ok=%s media=%.2f fen=%s piores=%s" % (
            purpose,
            "sim" if found.ok else "nao",
            _mean_confidence(found),
            found.fen or "-",
            worst,
        )
        if self._read_gate.allow(text, time.monotonic()):
            _LOG.info(text)

    def _say(self, text: str) -> None:
        self.messages.append(text)


_LOST_MEAN_CONFIDENCE = 0.35
_LOOK_AGAIN_MS = 1000


def _piece_diff_count(board: chess.Board, placement: dict[str, str]) -> int:
    current = {chess.square_name(square): piece.symbol() for square, piece in board.piece_map().items()}
    squares = set(current) | set(placement)
    return sum(1 for square in squares if current.get(square) != placement.get(square))


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
