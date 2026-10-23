"""Leitura da posição por um modelo local, uma casa de cada vez.

O retângulo marcado pode vir com uma margem pequena. Vários recortes são
provados e fica o que tem a pior casa mais segura. Se alguma casa ficar
ambígua, o tabuleiro inteiro é recusado.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from chesscoach.types import Frame, Orientation, Theme
from chesscoach.vision.square_model import INPUT_SIZE, LABELS, MIN_CONFIDENCE, UNKNOWN, predict_squares
from chesscoach.vision.squares import _span, square_name

_MAX_CORNER_DISTANCE = 60.0


@dataclass
class SquareRead:
    square: str
    piece: str | None
    confidence: float


@dataclass
class BoardRead:
    squares: list[SquareRead]
    ok: bool
    fen: str | None


class PieceClassifier:
    def read_board(
        self,
        frame: Frame,
        orientation: Orientation,
        theme: Theme,
        side_to_move: str = "w",
    ) -> BoardRead: ...


class TemplateClassifier:
    def read_board(
        self,
        frame: Frame,
        orientation: Orientation,
        theme: Theme,
        side_to_move: str = "w",
    ) -> BoardRead:
        del theme
        image = frame.image
        if image.ndim != 3 or image.shape[0] < 64 or image.shape[1] < 64:
            return BoardRead([], False, None)
        ranked: list[tuple[float, float, list[SquareRead]]] = []
        for crop in _candidates(image):
            ranked.append(_score_crop(crop, orientation))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        min_confidence, _mean, squares = ranked[0]
        ok = min_confidence >= MIN_CONFIDENCE
        placement = {item.square: item.piece for item in squares if item.piece}
        fen = _fen(placement, side_to_move) if ok else None
        if fen is None:
            ok = False
        return BoardRead(squares=squares, ok=ok, fen=fen)


def _score_crop(image: np.ndarray, orientation: Orientation) -> tuple[float, float, list[SquareRead]]:
    tiles = _tiles(image)
    index, confidence = predict_squares(tiles)
    confidence = confidence.copy()
    confidence[index == UNKNOWN] = 0.0
    confidence[_garish(tiles, index)] = 0.0
    outliers = _outlier_mask(image)
    confidence[outliers] = 0.0
    squares: list[SquareRead] = []
    for row in range(8):
        for col in range(8):
            slot = row * 8 + col
            label = LABELS[int(index[slot])]
            piece = label if label not in ("", "?") and confidence[slot] >= MIN_CONFIDENCE else None
            squares.append(SquareRead(square_name(row, col, orientation), piece, float(confidence[slot])))
    return float(confidence.min()), float(confidence.mean()), squares


def _candidates(image: np.ndarray) -> list[np.ndarray]:
    found = [image]
    height, width = image.shape[:2]
    for inset in (0.02, 0.035, 0.05):
        y0, x0 = int(height * inset), int(width * inset)
        y1, x1 = height - y0, width - x0
        if y1 - y0 >= 80 and x1 - x0 >= 80:
            found.append(image[y0:y1, x0:x1])
    for dy, dx in ((-0.03, 0.0), (0.03, 0.0), (0.0, -0.03), (0.0, 0.03)):
        matrix = np.float32([[1, 0, dx * width], [0, 1, dy * height]])
        shifted = cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        found.append(shifted)
    return found


def _tiles(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    tiles = np.empty((64, INPUT_SIZE, INPUT_SIZE, 3), dtype=np.uint8)
    slot = 0
    for row in range(8):
        y0, y1 = _span(row, height)
        for col in range(8):
            x0, x1 = _span(col, width)
            cell = image[y0:y1, x0:x1]
            if cell.size == 0:
                tiles[slot] = 0
            else:
                tiles[slot] = cv2.resize(cell, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)
            slot += 1
    return tiles


def _garish(tiles: np.ndarray, index: np.ndarray) -> np.ndarray:
    """Peça pintada de uma cor forte não é peça de tabuleiro 2D."""
    inner = tiles[:, 10:38, 10:38].astype(np.float32)
    span = inner.max(axis=3) - inner.min(axis=3)
    saturation = span / np.maximum(inner.max(axis=3), 1.0)
    colorful = saturation.mean(axis=(1, 2)) > 0.72
    piece = (index != 0) & (index != UNKNOWN)
    return piece & colorful


def _outlier_mask(image: np.ndarray) -> np.ndarray:
    colors = _corner_colors(image)
    luminance = colors.mean(axis=1)
    centers = np.stack([colors[int(luminance.argmax())], colors[int(luminance.argmin())]]).astype(np.float32)
    for _ in range(6):
        distance = np.mean(np.abs(colors[:, None, :] - centers[None, :, :]), axis=2)
        assign = distance.argmin(axis=1)
        for group in range(2):
            chosen = colors[assign == group]
            if len(chosen):
                centers[group] = chosen.mean(axis=0)
    distance = np.mean(np.abs(colors[:, None, :] - centers[None, :, :]), axis=2).min(axis=1)
    return distance > _MAX_CORNER_DISTANCE


def _corner_colors(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    colors = np.zeros((64, 3), dtype=np.float32)
    slot = 0
    for row in range(8):
        y0, y1 = _span(row, height)
        for col in range(8):
            x0, x1 = _span(col, width)
            colors[slot] = _corner_median(image[y0:y1, x0:x1])
            slot += 1
    return colors


def _corner_median(cell: np.ndarray) -> np.ndarray:
    if cell.size == 0:
        return np.zeros(3, dtype=np.float32)
    cell_height, cell_width = cell.shape[:2]
    margin = max(2, cell_height // 12)
    patches = (
        cell[:margin, :margin],
        cell[:margin, -margin:],
        cell[-margin:, :margin],
        cell[-margin:, -margin:],
    )
    pixels = np.concatenate([patch.reshape(-1, 3) for patch in patches if patch.size], axis=0)
    return np.median(pixels, axis=0).astype(np.float32)


def _fen(placement: dict[str, str], side_to_move: str) -> str | None:
    import chess

    ranks = []
    for rank in range(8, 0, -1):
        empty = 0
        row = ""
        for file_index in range(8):
            name = "abcdefgh"[file_index] + str(rank)
            piece = placement.get(name)
            if piece is None:
                empty += 1
                continue
            if empty:
                row += str(empty)
                empty = 0
            row += piece
        if empty:
            row += str(empty)
        ranks.append(row)
    turn = "w" if side_to_move.startswith("w") else "b"
    rights = _castling(placement)
    fen = f"{'/'.join(ranks)} {turn} {rights} - 0 1"
    try:
        chess.Board(fen)
    except ValueError:
        return None
    return fen


def _castling(placement: dict[str, str]) -> str:
    rights = ""
    if placement.get("e1") == "K" and placement.get("h1") == "R":
        rights += "K"
    if placement.get("e1") == "K" and placement.get("a1") == "R":
        rights += "Q"
    if placement.get("e8") == "k" and placement.get("h8") == "r":
        rights += "k"
    if placement.get("e8") == "k" and placement.get("a8") == "r":
        rights += "q"
    return rights or "-"
