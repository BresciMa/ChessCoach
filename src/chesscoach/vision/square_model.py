"""Modelo local das 64 casas. A imagem do tabuleiro não sai da máquina."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import numpy as np

INPUT_SIZE = 48
LABELS = ("", "K", "Q", "R", "B", "N", "P", "k", "q", "r", "b", "n", "p", "?")
UNKNOWN = LABELS.index("?")
MIN_CONFIDENCE = 0.55
_MODEL = Path(__file__).resolve().parent / "pieces" / "model" / "squares.onnx"


@cache
def _session():
    import onnxruntime as ort

    if not _MODEL.is_file():
        raise FileNotFoundError(_MODEL)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(_MODEL), options, providers=["CPUExecutionProvider"])


def predict_squares(tiles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """`tiles` é N×48×48×3 em RGB. Devolve o índice da classe e a probabilidade dela."""
    blob = np.transpose(tiles.astype(np.float32) / 255.0, (0, 3, 1, 2))
    logits = _session().run(None, {"squares": blob})[0]
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    probs = exp / exp.sum(axis=1, keepdims=True)
    index = probs.argmax(axis=1).astype(np.int64)
    chosen = probs[np.arange(len(index)), index]
    return index, chosen.astype(np.float32)
