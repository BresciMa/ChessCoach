"""Cores das casas e desenho do tabuleiro usado nos testes.

As peças são o conjunto Cburnett do Lichess. As cores das casas mudam com o tema.
Um conjunto de peças diferente fica abaixo da margem e o tabuleiro é recusado.
Acompanhar desde a posição inicial não usa estes desenhos: só a diferença entre casas.
"""

from __future__ import annotations

import numpy as np

from chesscoach.types import Orientation, Theme
from chesscoach.vision.squares import square_to_row_col

LIGHT = {
    Theme.LICHESS_2D: (240, 217, 181),
    Theme.CHESSCOM_2D: (235, 236, 208),
}
DARK = {
    Theme.LICHESS_2D: (181, 136, 99),
    Theme.CHESSCOM_2D: (119, 149, 86),
}


def square_color(name: str, theme: Theme) -> tuple[int, int, int]:
    file_index = ord(name[0]) - 97
    rank_index = int(name[1]) - 1
    light = (file_index + rank_index) % 2 == 1
    return LIGHT[theme] if light else DARK[theme]


def render_board(
    placement: dict[str, str],
    theme: Theme,
    orientation: Orientation = Orientation.WHITE_AT_BOTTOM,
    size: int = 320,
) -> np.ndarray:
    from chesscoach.vision.sprites import composite

    image = np.zeros((size, size, 3), dtype=np.uint8)
    cell = size // 8
    for row in range(8):
        for col in range(8):
            name = _name_at(row, col, orientation)
            y0, x0 = row * cell, col * cell
            image[y0 : y0 + cell, x0 : x0 + cell] = square_color(name, theme)
            piece = placement.get(name)
            if piece:
                composite(image[y0 : y0 + cell, x0 : x0 + cell], piece)
    return image


def placement_from_board(board) -> dict[str, str]:
    import chess

    found = {}
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            found[chess.square_name(square)] = piece.symbol()
    return found


def _name_at(row: int, col: int, orientation: Orientation) -> str:
    from chesscoach.vision.squares import square_name

    return square_name(row, col, orientation)


def square_of(name: str, orientation: Orientation) -> tuple[int, int]:
    return square_to_row_col(name, orientation)
