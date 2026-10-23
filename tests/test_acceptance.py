"""Aceite do produto. Itens de tela ficam em test_ui.py."""

import os

import chess

from chesscoach.coach.session import CoachSession
from chesscoach.config import AppConfig, load_config
from chesscoach.engine.uci import EngineResult
from chesscoach.messages import MSG_BOARD_BACK, MSG_BOARD_LOST, MSG_NEED_ROI, MSG_UNREADABLE, TRAINING_TEXT
from chesscoach.types import Frame, Level, Message, Orientation, Rect, Theme
from chesscoach.vision.themes import placement_from_board, render_board
from tests.images import board_image, solid


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


def _session(images, level=Level.LEVEL_2, arrows=True) -> tuple[CoachSession, FakeEngine, FakeLlm]:
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
    session = CoachSession(config, capture=ScriptedCapture(images), engine=engine, llm=llm)
    return session, engine, llm


def test_the_users_own_move_is_quiet_and_the_reply_is_not():
    start = board_image(chess.Board())
    white = chess.Board()
    white.push_san("e4")
    black = white.copy()
    black.push_san("e5")
    own = board_image(white)
    reply = board_image(black)
    session, engine, llm = _session([start, own, own, own, reply, reply, reply])
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
    assert engine.calls == 1
    assert lines
    assert "O adversário acabou de jogar" in llm.prompts[-1][-1].content
    assert "Nh6" not in llm.prompts[-1][-1].content
    assert session.overlay_state().arrow is None


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


def test_training_text_is_the_specified_copy():
    assert "responsabilidade de não usar o Chess Coach" in TRAINING_TEXT
    assert "não se esconde de anti-cheat" in TRAINING_TEXT
    assert "partida competitiva" in TRAINING_TEXT
