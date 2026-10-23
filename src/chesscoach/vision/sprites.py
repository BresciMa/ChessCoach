"""Peças Cburnett do Lichess, já rasterizadas.

O classificador compara a foto da casa com estes desenhos. O fundo de cada
casa (inclusive o amarelo do último lance) é estimado na hora.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import cv2
import numpy as np

SPRITE_SIZE = 64
_DIRECTORY = Path(__file__).resolve().parent / "pieces" / "lichess"
_FILES = {
    "K": "wK.png",
    "Q": "wQ.png",
    "R": "wR.png",
    "B": "wB.png",
    "N": "wN.png",
    "P": "wP.png",
    "k": "bK.png",
    "q": "bQ.png",
    "r": "bR.png",
    "b": "bB.png",
    "n": "bN.png",
    "p": "bP.png",
}


@cache
def sprites() -> dict[str, np.ndarray]:
    """RGBA uint8 na ordem RGB do restante do app, com o fundo transparente."""
    found: dict[str, np.ndarray] = {}
    for symbol, name in _FILES.items():
        path = _DIRECTORY / name
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None or image.ndim != 3 or image.shape[2] != 4:
            raise FileNotFoundError(path)
        rgba = image[:, :, [2, 1, 0, 3]]
        found[symbol] = np.ascontiguousarray(rgba)
    return found


def composite(square: np.ndarray, symbol: str) -> None:
    """Desenha a peça por cima da cor que já está na casa."""
    sprite = sprites()[symbol]
    height, width = square.shape[:2]
    resized = cv2.resize(sprite, (width, height), interpolation=cv2.INTER_AREA)
    color = resized[:, :, :3].astype(np.float32)
    alpha = resized[:, :, 3:4].astype(np.float32) / 255.0
    base = square.astype(np.float32)
    square[:] = np.clip(color * alpha + base * (1.0 - alpha), 0, 255).astype(np.uint8)
