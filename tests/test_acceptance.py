"""Aceite do produto. Itens de tela ficam em test_ui.py."""

import os

import chess
import numpy as np

from chesscoach.coach.session import CoachSession
from chesscoach.config import AppConfig, load_config
from chesscoach.engine.uci import EngineResult
from chesscoach.messages import (
    MSG_BOARD_BACK,
    MSG_BOARD_LOST,
    MSG_ENGINE_SILENT,
    MSG_NEED_ROI,
    MSG_NO_ENGINE,
    MSG_UNREADABLE,
    TRAINING_TEXT,
)
from chesscoach.types import Frame, Level, Message, Orientation, Reason, Rect, Theme
from chesscoach.vision.classifier import BoardRead, SquareRead, TemplateClassifier
from chesscoach.vision.themes import placement_from_board, render_board
from tests.images import board_image, solid, tint


class FakeEngine:
    def __init__(self, result=None):
        self.calls = 0
        self.result = result or EngineResult(35, ["g8h6"])

    def analyze(self, fen: str):
        self.calls += 1
        return self.result


class FakeLlm:
    def __init__(self):
        self.prompts: list[list[Message]] = []

    def complete(self, messages, model: str) -> str:
        self.prompts.append(messages)
        return messages[-1].content


class ScriptedCapture:
    def __init__(self, images):
        self.images = list(images)
        self.calls = 0

    def grab(self, monitor, region):
        image = self.images[min(self.calls, len(self.images) - 1)]
        self.calls += 1
        from chesscoach.types import Frame

        return Frame(image, 0)


def _session(images, level=Level.LEVEL_2, arrows=True, classifier=None) -> tuple[CoachSession, FakeEngine, FakeLlm]:
    os.environ["GEMINI_API_KEY"] = "teste-nao-e-chave-real"
    engine = FakeEngine()
    llm = FakeLlm()
    config = AppConfig(
        training_accepted=True,
        level=level,
        roi=Rect(0, 0, 320, 320),
        arrows_enabled=arrows,
        orientation=Orientation.WHITE_AT_BOTTOM,
    )
    session = CoachSession(
        config,
        capture=ScriptedCapture(images),
        classifier=classifier,
        engine=engine,
        llm=llm,
    )
    return session, engine, llm


def _cover(seed: int) -> np.ndarray:
    image = np.zeros((320, 320, 3), dtype=np.uint8)
    image[:, :160] = ((seed * 80) % 180 + 40, 12, 12)
    image[:, 160:] = (12, (seed * 80) % 180 + 40, 170)
    return image


class _FailOnce:
    def __init__(self):
        self.inner = TemplateClassifier()
        self.calls = 0

    def read_board(self, frame, orientation, theme, side_to_move="w"):
        self.calls += 1
        if self.calls == 1:
            return BoardRead([], False, None)
        return self.inner.read_board(frame, orientation, theme, side_to_move)


def test_the_users_own_move_is_quiet_and_the_reply_is_not(caplog):
    import logging
    start = board_image(chess.Board())
    white = chess.Board()
    white.push_san("e4")
    black = white.copy()
    black.push_san("e5")
    own = board_image(white)
    reply = board_image(black)
    session, engine, llm = _session([start, own, own, own, reply, reply, reply])
    with caplog.at_level(logging.INFO, logger="chesscoach.session"):
        session.poll(0)
        session.poll(250)
        session.poll(350)
        session.poll(750)
        assert engine.calls == 0
        assert session.messages == []
        assert session.game.sans == ["e4"]
        session.poll(1000)
        session.poll(1100)
        lines = session.poll(1500)
    assert sum(record.message == "movimento detectado" for record in caplog.records) == 2
    assert engine.calls == 1
    assert lines
    assert "O adversário acabou de jogar" in llm.prompts[-1][-1].content
    assert "Nh6" not in llm.prompts[-1][-1].content
    assert session.overlay_state().arrow is None


def test_a_deferred_comment_waits_and_a_changed_position_is_dropped(caplog):
    import logging

    session, engine, llm = _session([board_image(chess.Board())], level=Level.LEVEL_1)
    session.defer_comments = True
    with caplog.at_level(logging.INFO, logger="chesscoach.session"):
        session._request_comment(Reason.MOVE_CONFIRMED, None)
    assert engine.calls == 0
    assert llm.prompts == []
    first = session.take_comment()
    assert first is not None
    session._request_comment(Reason.HINT_REQUESTED, None)
    assert session.take_comment() is None
    prepared = session.prepare_comment(*first[:2])
    session.game.apply(session.game.parse_san("e4"))
    session._request_comment(Reason.MOVE_CONFIRMED, None)
    with caplog.at_level(logging.INFO, logger="chesscoach.session"):
        assert session.commit_comment(prepared) is False
    assert any(record.message == "comentario descartado" for record in caplog.records)
    assert session.messages == []
    session.release_comment()
    waiting = session.take_comment()
    assert waiting is not None
    assert waiting[0] == Reason.MOVE_CONFIRMED
    assert waiting[2] == session.game.fen


def test_the_arrow_stays_on_its_mark_and_goes_when_the_piece_moves(caplog):
    import logging

    start = board_image(chess.Board())
    white = chess.Board()
    white.push_san("e4")
    black = white.copy()
    black.push_san("e5")
    own = board_image(white)
    reply = board_image(black)
    marked = tint(reply, ["a2"])
    moved_board = black.copy()
    moved_board.push_san("Nf3")
    played = board_image(moved_board)
    moved_marked = tint(played, ["a2"])
    session, engine, _llm = _session(
        [
            start,
            own,
            own,
            own,
            reply,
            reply,
            reply,
            marked,
            marked,
            marked,
            moved_marked,
            moved_marked,
            moved_marked,
            played,
            played,
            played,
        ],
        level=Level.LEVEL_1,
        arrows=True,
    )
    engine.result = EngineResult(22, ["g1f3"])
    with caplog.at_level(logging.INFO, logger="chesscoach.session"):
        session.poll(0)
        session.poll(250)
        session.poll(350)
        session.poll(750)
        session.poll(1000)
        session.poll(1100)
        session.poll(1500)
        assert session.overlay_state().arrow == "Nf3"
        session.poll(1750)
        session.poll(1850)
        session.poll(2250)
        assert session.overlay_state().arrow == "Nf3"
        assert session.game.sans == ["e4", "e5"]
        session.poll(2500)
        session.poll(2600)
        session.poll(3000)
        assert session.overlay_state().arrow is None
        assert session.game.sans == ["e4", "e5"]
        session.poll(3250)
        session.poll(3350)
        session.poll(3750)
    messages = [record.message for record in caplog.records]
    assert "seta na referencia" in messages
    assert "seta apagada" in messages
    assert session.overlay_state().arrow is None
    assert session.game.sans == ["e4", "e5", "Nf3"]


def test_hint_reveals_one_move_and_master_does_not_suggest_the_next():
    start = board_image(chess.Board())
    after_board = chess.Board()
    after_board.push_san("e4")
    after = board_image(after_board)
    reply_board = after_board.copy()
    reply_board.push_san("e5")
    reply = board_image(reply_board)
    session, _, llm = _session([start, after, after, after], level=Level.LEVEL_2, arrows=True)
    session.poll(0)
    session.poll(250)
    session.poll(350)
    session.poll(750)
    assert session.messages == []
    assert session.overlay_state().arrow is None
    session.request_hint()
    assert "Nh6" in llm.prompts[-1][-1].content
    assert session.overlay_state().arrow == "Nh6"

    master, _, master_llm = _session(
        [start, after, after, after, reply, reply, reply],
        level=Level.MASTER,
        arrows=True,
    )
    assert master.poll(0) == []
    assert master.poll(250) == []
    assert master.poll(350) == []
    assert master.poll(750) == []
    assert master.poll(1000) == []
    assert master.poll(1100) == []
    lines = master.poll(1500)
    assert lines
    assert "Nh6" not in master_llm.prompts[-1][-1].content
    assert master.overlay_state().arrow is None


def test_a_covering_window_is_announced_once_and_a_real_board_reconnects():
    start = board_image(chess.Board())
    green = solid((0, 255, 0))
    mid = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6"):
        mid.push_san(san)
    picture = board_image(mid)
    session, engine, llm = _session([start, green, green, green, picture, picture, picture])
    session.poll(0)
    session.poll(250)
    session.poll(350)
    assert session.poll(750) == [MSG_BOARD_LOST]
    assert session.poll(1000) == []
    assert session.poll(1100) == []
    assert session.poll(1500) == [MSG_BOARD_BACK]
    assert session.messages.count(MSG_BOARD_LOST) == 1
    assert session.game.board.board_fen() == mid.board_fen()
    assert engine.calls == 0
    assert llm.prompts == []


def test_a_failed_reread_stays_lost_without_repeating_the_message():
    start = board_image(chess.Board())
    green = solid((0, 255, 0))
    blue = solid((0, 0, 255))
    session, engine, _ = _session([start, green, green, green, blue, blue, blue])
    session.poll(0)
    session.poll(250)
    session.poll(350)
    session.poll(750)
    session.poll(1000)
    session.poll(1100)
    session.poll(1500)
    assert session.messages == [MSG_BOARD_LOST]
    assert session.game.board.fen() == chess.STARTING_FEN
    assert engine.calls == 0


def test_several_missed_moves_are_reread_and_the_advice_uses_the_new_position():
    start = chess.Board()
    start.push_san("e4")
    later = start.copy()
    for san in ("c6", "Nc3", "d5"):
        later.push_san(san)
    opening = board_image(start)
    picture = board_image(later)
    session, engine, llm = _session([opening, picture, picture, picture], level=Level.LEVEL_1)
    session.game.apply(session.game.parse_san("e4"))
    session.poll(0)
    session.poll(250)
    session.poll(350)
    lines = session.poll(750)
    assert MSG_BOARD_BACK not in lines
    assert MSG_BOARD_LOST not in session.messages
    assert session.game.sans == ["e4", "c6", "Nc3", "d5"]
    assert session.game.board.board_fen() == later.board_fen()
    assert engine.calls == 1
    assert lines
    assert "d5" in llm.prompts[-1][-1].content


def test_a_failed_read_keeps_the_requested_side_for_the_next_look():
    image = board_image(chess.Board())
    session, _, _ = _session([image])
    board = chess.Board()
    board.push_san("e4")
    session.classifier = _FailThenHonorSide(board)
    assert session.read_now(Frame(image, 0), "b") == MSG_UNREADABLE
    assert session.game.board.turn == chess.WHITE
    session.tracker.last_image = image
    session._reconnect(0)
    assert session.game.board.turn == chess.BLACK
    assert session.game.board.piece_at(chess.E4) is not None
    assert session._forced_side is None
    session._forced_side = "b"
    session.follow_from_start()
    assert session._forced_side is None
    assert session.game.board.fen() == chess.STARTING_FEN


class _FailThenHonorSide:
    def __init__(self, board: chess.Board):
        self.board = board
        self.calls = 0

    def read_board(self, frame, orientation, theme, side_to_move="w"):
        self.calls += 1
        if self.calls == 1:
            return BoardRead([], False, None)
        parts = self.board.fen().split(" ")
        parts[1] = "b" if str(side_to_move).startswith("b") else "w"
        squares = [
            SquareRead(chess.square_name(square), piece.symbol(), 0.99)
            for square, piece in self.board.piece_map().items()
        ]
        return BoardRead(squares, True, " ".join(parts))


def test_calibration_stores_orientation_when_qt_returns_text(tmp_path):
    path = tmp_path / "config.json"
    session, _, _ = _session([board_image(chess.Board())])
    session.config_path = path
    error = session.set_calibration(0, Rect(0, 0, 320, 320), "black_at_bottom")
    assert error is None
    assert session.config.orientation == Orientation.BLACK_AT_BOTTOM
    assert load_config(path).orientation == Orientation.BLACK_AT_BOTTOM


def test_set_level_is_written_when_the_session_has_a_config_path(tmp_path):
    path = tmp_path / "config.json"
    session, _, _ = _session([board_image(chess.Board())])
    session.config_path = path
    session.set_level(Level.MASTER)
    assert load_config(path).level == Level.MASTER


def test_follow_without_a_rectangle_is_refused():
    session, _, _ = _session([board_image(chess.Board())])
    session.config.roi = None
    assert session.follow_from_start() == MSG_NEED_ROI


def test_low_confidence_read_does_not_replace_the_fen():
    session, _, _ = _session([board_image(chess.Board())])
    before = session.game.fen
    image = render_board(placement_from_board(chess.Board()), Theme.LICHESS_2D)
    image = image.copy()
    image[0:40, 0:40] = (0, 0, 255)
    message = session.read_now(Frame(image, 0))
    assert message == MSG_UNREADABLE
    assert session.game.fen == before


def test_a_moving_window_goes_blind_and_the_same_board_wakes_the_coach():
    start = board_image(chess.Board())
    windows = [_cover(index) for index in range(11)]
    session, engine, _ = _session([start, *windows, start])
    session.poll(0)
    for moment in (250, 350, 450, 550, 650, 750, 850, 950, 1050, 1150, 1250):
        session.poll(moment)
    assert session.blind is True
    session.poll(1500)
    assert session.blind is False
    assert session._board_lost is False
    assert session.game.fen == chess.STARTING_FEN
    assert engine.calls == 0


def test_a_still_window_wakes_when_the_known_board_returns():
    start = board_image(chess.Board())
    cover = _cover(3)
    session, engine, _ = _session([start, cover, cover, cover, cover, cover, start])
    session.poll(0)
    session.poll(250)
    session.poll(350)
    assert session.poll(750) == [MSG_BOARD_LOST]
    assert session.blind is True
    session.poll(1000)
    session.poll(1250)
    assert session.blind is True
    session.poll(1500)
    assert session.blind is False
    assert MSG_BOARD_BACK not in session.messages
    assert session.game.fen == chess.STARTING_FEN
    assert engine.calls == 0


def test_a_failed_read_is_tried_again_while_the_picture_stays():
    start = chess.Board()
    start.push_san("e4")
    later = start.copy()
    for san in ("c6", "Nc3", "d5"):
        later.push_san(san)
    flaky = _FailOnce()
    session, engine, _ = _session(
        [board_image(start), board_image(later), board_image(later), board_image(later), board_image(later), board_image(later)],
        classifier=flaky,
    )
    session.game.apply(session.game.parse_san("e4"))
    session.poll(0)
    session.poll(250)
    session.poll(350)
    assert MSG_BOARD_LOST in session.poll(750)
    assert session.blind is True
    assert session.game.sans == ["e4"]
    session.poll(1000)
    assert session.blind is True
    assert flaky.calls == 1
    session.poll(1750)
    assert session.blind is False
    assert session.game.sans == ["e4", "c6", "Nc3", "d5"]
    assert engine.calls == 0


def test_reading_or_following_wakes_the_coach():
    image = board_image(chess.Board())
    session, _, _ = _session([image])
    session.blind = True
    session._board_lost = True
    assert session.read_now(Frame(image, 0)) is None
    assert session.blind is False
    assert session._board_lost is False

    session.blind = True
    session._board_lost = True
    assert session.follow_from_start() is None
    assert session.blind is False
    assert session._board_lost is False

    session.blind = True
    broken = image.copy()
    broken[0:40, 0:40] = (0, 0, 255)
    assert session.read_now(Frame(broken, 0)) == MSG_UNREADABLE
    assert session.blind is True


class _StaticBoard:
    def __init__(self, board: chess.Board):
        self.board = board

    def read_board(self, frame, orientation, theme, side_to_move="w"):
        squares = [
            SquareRead(chess.square_name(square), piece.symbol(), 0.99)
            for square, piece in self.board.piece_map().items()
        ]
        return BoardRead(squares, True, self.board.fen())


class _NoneEngine:
    def analyze(self, fen):
        return None


def test_a_square_that_cannot_be_a_move_does_not_call_the_coach():
    session, engine, llm = _session([board_image(chess.Board())])
    for san in ("e4", "e5", "Nf3", "Bc5"):
        session.game.apply(session.game.parse_san(san))
    before = session.game.fen
    wrong = session.game.board.copy()
    wrong.remove_piece_at(chess.E5)
    wrong.set_piece_at(chess.E5, chess.Piece.from_symbol("B"))
    session.classifier = _StaticBoard(wrong)
    session.tracker.last_image = board_image(session.game.board)
    session._reconnect(0)
    assert session.game.fen == before
    assert engine.calls == 0
    assert llm.prompts == []


def test_a_configured_engine_that_stays_quiet_is_not_called_missing():
    session, _, llm = _session([board_image(chess.Board())], level=Level.LEVEL_1)
    session.engine = _NoneEngine()
    session.config.stockfish_path = r"C:\Games\stockfish.exe"
    session._comment(Reason.MOVE_CONFIRMED, None)
    assert session.messages[-1] == MSG_ENGINE_SILENT
    assert MSG_NO_ENGINE not in session.messages
    assert llm.prompts == []


def test_the_coach_line_records_the_model_time(caplog):
    import logging

    session, _, llm = _session([board_image(chess.Board())], level=Level.LEVEL_1)
    with caplog.at_level(logging.INFO, logger="chesscoach"):
        session._comment(Reason.MOVE_CONFIRMED, None)
    assert llm.prompts
    assert any("llm_ms=" in record.message and "motor_ms=" in record.message for record in caplog.records)
    assert any(record.message.startswith("gemini ") for record in caplog.records)


def test_training_text_is_the_specified_copy():
    assert "responsabilidade de não usar o Chess Coach" in TRAINING_TEXT
    assert "não se esconde de anti-cheat" in TRAINING_TEXT
    assert "partida competitiva" in TRAINING_TEXT
