"""Imagens de tabuleiro para os testes, sem tela."""

from __future__ import annotations

import chess
import numpy as np

from chesscoach.types import Frame, Orientation, Theme
from chesscoach.vision.squares import square_to_row_col
from chesscoach.vision.themes import render_board, placement_from_board


def board_image(board: chess.Board, orientation: Orientation = Orientation.WHITE_AT_BOTTOM) -> np.ndarray:
    return render_board(placement_from_board(board), Theme.LICHESS_2D, orientation)


def frame(image: np.ndarray, time_ms: int) -> Frame:
    return Frame(image=image, time_ms=time_ms)


def tint(image: np.ndarray, squares: list[str], orientation: Orientation = Orientation.WHITE_AT_BOTTOM) -> np.ndarray:
    painted = image.copy()
    cell = painted.shape[0] // 8
    for name in squares:
        row, col = square_to_row_col(name, orientation)
        y0, x0 = row * cell, col * cell
        painted[y0 : y0 + cell, x0 : x0 + cell, 2] = np.clip(
            painted[y0 : y0 + cell, x0 : x0 + cell, 2].astype(np.int16) + 80,
            0,
            255,
        )
    return painted


def solid(color: tuple[int, int, int], size: int = 320) -> np.ndarray:
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:, :] = color
    return image
