from pathlib import Path

import chess
import cv2
import numpy as np

from chesscoach.types import Frame, Orientation, Theme
from chesscoach.vision.classifier import TemplateClassifier
from chesscoach.vision.themes import placement_from_board, render_board

_FIXTURE = Path(__file__).parent / "fixtures" / "lichess_e4_e6.png"
_SEEN_FEN = "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"


def test_each_theme_reads_the_starting_position():
    classifier = TemplateClassifier()
    for theme in (Theme.LICHESS_2D, Theme.CHESSCOM_2D):
        image = render_board(placement_from_board(chess.Board()), theme)
        found = classifier.read_board(Frame(image, 0), Orientation.WHITE_AT_BOTTOM, theme, "w")
        assert found.ok
        assert found.fen == chess.STARTING_FEN


def test_black_at_the_bottom_still_reads_the_same_fen():
    classifier = TemplateClassifier()
    image = render_board(
        placement_from_board(chess.Board()),
        Theme.LICHESS_2D,
        Orientation.BLACK_AT_BOTTOM,
    )
    found = classifier.read_board(Frame(image, 0), Orientation.BLACK_AT_BOTTOM, Theme.LICHESS_2D, "w")
    assert found.ok
    assert found.fen == chess.STARTING_FEN


def test_one_corrupt_square_rejects_the_whole_board():
    classifier = TemplateClassifier()
    image = render_board(placement_from_board(chess.Board()), Theme.LICHESS_2D)
    image = image.copy()
    image[0:40, 0:40] = (0, 0, 255)
    found = classifier.read_board(Frame(image, 0), Orientation.WHITE_AT_BOTTOM, Theme.LICHESS_2D, "w")
    assert found.ok is False
    assert found.fen is None


def test_a_scribble_in_the_middle_of_a_square_is_not_a_piece():
    classifier = TemplateClassifier()
    image = render_board(placement_from_board(chess.Board()), Theme.LICHESS_2D).copy()
    image[125:155, 125:155] = (255, 0, 0)
    found = classifier.read_board(Frame(image, 0), Orientation.WHITE_AT_BOTTOM, Theme.LICHESS_2D, "w")
    assert found.ok is False
    assert found.fen is None


def test_a_margin_around_the_real_board_still_reads():
    classifier = TemplateClassifier()
    bgr = cv2.imread(str(_FIXTURE), cv2.IMREAD_COLOR)
    image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    pad = 14
    canvas = np.full((image.shape[0] + 2 * pad, image.shape[1] + 2 * pad, 3), 28, np.uint8)
    canvas[pad:-pad, pad:-pad] = image
    found = classifier.read_board(Frame(canvas, 0), Orientation.WHITE_AT_BOTTOM, Theme.LICHESS_2D, "w")
    assert found.ok
    assert found.fen == _SEEN_FEN


def test_a_real_lichess_board_with_highlights_and_coordinates():
    classifier = TemplateClassifier()
    bgr = cv2.imread(str(_FIXTURE), cv2.IMREAD_COLOR)
    image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    found = classifier.read_board(Frame(image, 0), Orientation.WHITE_AT_BOTTOM, Theme.LICHESS_2D, "w")
    assert found.ok
    assert found.fen == _SEEN_FEN
