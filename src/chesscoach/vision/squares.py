"""Assinatura das 64 casas. O limiar olha o miolo de cada casa."""

from __future__ import annotations

import numpy as np

from chesscoach.types import Orientation

SQUARE_DIFF_THRESHOLD = 12.0


def square_signature(image: np.ndarray) -> np.ndarray:
    """Média RGB do miolo de cada casa, em ordem visual (linha de cima, da esquerda para a direita)."""
    height, width = image.shape[:2]
    signature = np.zeros((64, 3), dtype=np.float32)
    index = 0
    for row in range(8):
        y0, y1 = _span(row, height)
        for col in range(8):
            x0, x1 = _span(col, width)
            patch = image[y0:y1, x0:x1]
            inner = _inner(patch)
            signature[index] = inner.mean(axis=(0, 1))
            index += 1
    return signature


def changed_indices(previous: np.ndarray, current: np.ndarray, threshold: float = SQUARE_DIFF_THRESHOLD) -> list[int]:
    delta = np.mean(np.abs(previous - current), axis=1)
    return [index for index, value in enumerate(delta) if float(value) > threshold]


def signatures_similar(previous: np.ndarray, current: np.ndarray, threshold: float = SQUARE_DIFF_THRESHOLD) -> bool:
    return not changed_indices(previous, current, threshold)


def index_to_square(index: int, orientation: Orientation) -> str:
    return square_name(index // 8, index % 8, orientation)


def square_name(row: int, col: int, orientation: Orientation) -> str:
    if orientation == Orientation.WHITE_AT_BOTTOM:
        file_index = col
        rank = 8 - row
    else:
        file_index = 7 - col
        rank = row + 1
    return "abcdefgh"[file_index] + str(rank)


def square_to_row_col(name: str, orientation: Orientation) -> tuple[int, int]:
    file_index = ord(name[0]) - 97
    rank = int(name[1])
    if orientation == Orientation.WHITE_AT_BOTTOM:
        return 8 - rank, file_index
    return rank - 1, 7 - file_index


def _span(index: int, size: int) -> tuple[int, int]:
    start = index * size // 8
    end = (index + 1) * size // 8
    return start, end


def _inner(patch: np.ndarray) -> np.ndarray:
    height, width = patch.shape[:2]
    y0 = height // 4
    x0 = width // 4
    y1 = height - y0
    x1 = width - x0
    if y1 <= y0 or x1 <= x0:
        return patch
    return patch[y0:y1, x0:x1]
