"""Treina o classificador local das casas e grava squares.onnx.

Usa os SVG 2D do Lichess. A imagem de um tabuleiro real não entra no treino.
Rode com o Python do projeto, depois que torch e onnx estiverem instalados:

    .\\.venv\\Scripts\\python.exe tools/train_square_model.py
"""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import torch
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
from torch import nn

from chesscoach.vision.square_model import INPUT_SIZE, LABELS

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "tools" / ".piece-cache"
MODEL = ROOT / "src" / "chesscoach" / "vision" / "pieces" / "model" / "squares.onnx"
SETS = ("cburnett", "merida", "alpha", "chessnut", "companion", "gioco", "reillycraig", "maestro")
FILES = {
    "K": "wK.svg",
    "Q": "wQ.svg",
    "R": "wR.svg",
    "B": "wB.svg",
    "N": "wN.svg",
    "P": "wP.svg",
    "k": "bK.svg",
    "q": "bQ.svg",
    "r": "bR.svg",
    "b": "bB.svg",
    "n": "bN.svg",
    "p": "bP.svg",
}
WOOD = (
    (240, 217, 181),
    (181, 136, 99),
    (235, 236, 208),
    (119, 149, 86),
    (205, 210, 106),
    (170, 162, 58),
    (246, 230, 160),
    (150, 168, 104),
    (230, 205, 170),
    (140, 108, 76),
)
PER_CLASS = 480
EPOCHS = 12


class Net(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Flatten(),
            nn.Linear(64 * (INPUT_SIZE // 8) * (INPUT_SIZE // 8), 64),
            nn.ReLU(),
            nn.Linear(64, len(LABELS)),
        )

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return self.layers(batch)


def main() -> None:
    app = QApplication([])
    sprites = _load_sprites()
    print("conjuntos", sorted({key[0] for key in sprites}))
    rng = np.random.default_rng(7)
    images, targets = _samples(sprites, rng)
    net = Net()
    _fit(net, images, targets)
    _export(net)
    _check_fixture()
    app.exit()


def _load_sprites() -> dict[tuple[str, str], np.ndarray]:
    found: dict[tuple[str, str], np.ndarray] = {}
    local = ROOT / "src" / "chesscoach" / "vision" / "pieces" / "lichess"
    for symbol, filename in FILES.items():
        png = local / filename.replace(".svg", ".png")
        if png.is_file():
            image = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
            found[("cburnett", symbol)] = image[:, :, [2, 1, 0, 3]]
    for piece_set in SETS:
        for symbol, filename in FILES.items():
            if (piece_set, symbol) in found:
                continue
            path = CACHE / piece_set / filename
            if not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                url = f"https://raw.githubusercontent.com/lichess-org/lila/master/public/piece/{piece_set}/{filename}"
                try:
                    urllib.request.urlretrieve(url, path)
                except OSError as exc:
                    print("falhou", url, exc)
                    continue
            rendered = _render_svg(path)
            if rendered is not None:
                found[(piece_set, symbol)] = rendered
    expanded = dict(found)
    for key, sprite in found.items():
        expanded[(key[0] + "-flip", key[1])] = np.ascontiguousarray(sprite[:, ::-1, :])
    return expanded


def _render_svg(path: Path) -> np.ndarray | None:
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return None
    image = QImage(64, 64, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    raw = np.frombuffer(image.bits(), np.uint8, 64 * 64 * 4).reshape(64, 64, 4)
    return raw[:, :, [2, 1, 0, 3]].copy()


def _samples(sprites: dict[tuple[str, str], np.ndarray], rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    by_symbol: dict[str, list[np.ndarray]] = {label: [] for label in LABELS if label}
    for (_piece_set, symbol), sprite in sprites.items():
        by_symbol[symbol].append(sprite)
    images = []
    targets = []
    for label_index, label in enumerate(LABELS):
        for _ in range(PER_CLASS):
            if label == "":
                picture = _empty(rng)
            elif label == "?":
                picture = _unknown(rng, by_symbol)
            else:
                sprite = by_symbol[label][int(rng.integers(0, len(by_symbol[label])))]
                picture = _blit(sprite, _wood(rng), rng, float(rng.uniform(-8, 8)), float(rng.uniform(-8, 8)))
            images.append(_degrade(picture, rng, coordinates=label != "?"))
            targets.append(label_index)
    order = rng.permutation(len(images))
    return np.stack(images)[order], np.asarray(targets, np.int64)[order]


def _wood(rng: np.random.Generator) -> np.ndarray:
    base = np.asarray(WOOD[int(rng.integers(0, len(WOOD)))], np.float32)
    return np.clip(base + rng.normal(0, 8, size=3), 0, 255)


def _empty(rng: np.random.Generator) -> np.ndarray:
    return np.tile(_wood(rng), (64, 64, 1))


def _unknown(rng: np.random.Generator, by_symbol: dict[str, list[np.ndarray]]) -> np.ndarray:
    kind = int(rng.integers(0, 4))
    if kind == 0:
        return np.tile(rng.integers(0, 256, size=3).astype(np.float32), (64, 64, 1))
    canvas = _empty(rng)
    if kind == 1:
        return canvas * 0.25 + rng.integers(0, 256, size=canvas.shape)
    if kind == 2:
        y, x = rng.integers(0, 36, size=2)
        height, width = rng.integers(18, 40, size=2)
        canvas[int(y) : int(y + height), int(x) : int(x + width)] = rng.integers(0, 256, size=3)
        return canvas
    symbol = LABELS[int(rng.integers(1, len(LABELS) - 1))]
    sprite = by_symbol[symbol][int(rng.integers(0, len(by_symbol[symbol])))]
    shift = float(rng.choice([-36, -28, 28, 36]))
    return _blit(sprite, _wood(rng), rng, shift, float(rng.uniform(-8, 8)))


def _blit(sprite: np.ndarray, background: np.ndarray, rng: np.random.Generator, dx: float, dy: float) -> np.ndarray:
    canvas = np.tile(np.asarray(background, np.float32), (64, 64, 1))
    matrix = cv2.getRotationMatrix2D((32, 32), float(rng.uniform(-8, 8)), float(rng.uniform(0.82, 1.08)))
    matrix[0, 2] += dx
    matrix[1, 2] += dy
    warped = cv2.warpAffine(sprite, matrix, (64, 64), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    alpha = warped[:, :, 3:4].astype(np.float32) / 255.0
    color = warped[:, :, :3].astype(np.float32)
    return color * alpha + canvas * (1.0 - alpha)


def _degrade(image: np.ndarray, rng: np.random.Generator, coordinates: bool) -> np.ndarray:
    out = np.clip(image.astype(np.float32) * float(rng.uniform(0.84, 1.16)), 0, 255).astype(np.uint8)
    if coordinates and rng.random() < 0.45:
        text = str(rng.choice(list("abcdefgh12345678")))
        origins = ((2, 14), (46, 14), (2, 60), (42, 60))
        origin = origins[int(rng.integers(0, 4))]
        dark = bool(out[8, 8].mean() > 150)
        cv2.putText(out, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.38, (30, 30, 30) if dark else (240, 240, 240), 1, cv2.LINE_AA)
    if rng.random() < 0.35:
        quality = int(rng.integers(40, 90))
        _ok, encoded = cv2.imencode(".jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        out = cv2.cvtColor(cv2.imdecode(encoded, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    return cv2.resize(out, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)


def _fit(net: Net, images: np.ndarray, targets: np.ndarray) -> None:
    blob = torch.from_numpy(np.transpose(images.astype(np.float32) / 255.0, (0, 3, 1, 2)))
    goal = torch.from_numpy(targets)
    optimizer = torch.optim.Adam(net.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    net.train()
    count = len(goal)
    for epoch in range(EPOCHS):
        order = torch.randperm(count)
        total = 0.0
        correct = 0
        for start in range(0, count, 128):
            batch = order[start : start + 128]
            optimizer.zero_grad()
            logits = net(blob[batch])
            loss = loss_fn(logits, goal[batch])
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(batch)
            correct += int((logits.argmax(dim=1) == goal[batch]).sum())
        print(f"epoca {epoch + 1} perda {total / count:.3f} acerto {correct / count:.3f}")


def _export(net: Net) -> None:
    net.eval()
    dummy = torch.zeros(1, 3, INPUT_SIZE, INPUT_SIZE)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        net,
        dummy,
        str(MODEL),
        input_names=["squares"],
        output_names=["logits"],
        dynamic_axes={"squares": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    print("gravou", MODEL, MODEL.stat().st_size)


def _check_fixture() -> None:
    from chesscoach.vision.square_model import _session

    _session.cache_clear()
    import chess
    import cv2 as cv

    from chesscoach.types import Frame, Orientation, Theme
    from chesscoach.vision.classifier import TemplateClassifier
    from chesscoach.vision.themes import placement_from_board, render_board

    classifier = TemplateClassifier()
    synthetic = render_board(placement_from_board(chess.Board()), Theme.LICHESS_2D)
    found = classifier.read_board(Frame(synthetic, 0), Orientation.WHITE_AT_BOTTOM, Theme.LICHESS_2D, "w")
    print("sintetico", found.ok, found.fen)
    path = ROOT / "tests" / "fixtures" / "lichess_e4_e6.png"
    image = cv.cvtColor(cv.imread(str(path)), cv.COLOR_BGR2RGB)
    found = classifier.read_board(Frame(image, 0), Orientation.WHITE_AT_BOTTOM, Theme.LICHESS_2D, "w")
    print("foto", found.ok, found.fen)
    low = min(item.confidence for item in found.squares)
    print("pior casa", round(low, 3), [(item.square, item.piece, round(item.confidence, 2)) for item in found.squares if item.confidence < 0.8])


if __name__ == "__main__":
    main()
