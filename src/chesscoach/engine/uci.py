"""Stockfish via UCI. O executável não é empacotado."""

from __future__ import annotations

import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EngineResult:
    evaluation_cp: int
    uci_moves: list[str]

    @property
    def best_move(self) -> str | None:
        return self.uci_moves[0] if self.uci_moves else None


class ChessEngine:
    def analyze(self, fen: str) -> EngineResult | None: ...


class StockfishEngine:
    def __init__(self, path: str, movetime_ms: int = 300):
        self.path = path
        self.movetime_ms = movetime_ms

    def analyze(self, fen: str) -> EngineResult | None:
        if not self.path or not Path(self.path).is_file():
            return None
        try:
            process = subprocess.Popen(
                [self.path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except OSError:
            return None
        lines: queue.Queue[str | None] = queue.Queue()

        def _read() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                lines.put(line.rstrip("\n"))
            lines.put(None)

        thread = threading.Thread(target=_read, daemon=True)
        thread.start()
        try:
            assert process.stdin is not None
            process.stdin.write("uci\nsetoption name MultiPV value 3\nisready\n")
            process.stdin.write(f"position fen {fen}\n")
            process.stdin.write(f"go movetime {self.movetime_ms}\n")
            process.stdin.flush()
            collected = _collect(lines, timeout_s=max(2.0, self.movetime_ms / 1000 + 2))
            return parse_uci(collected)
        except (OSError, TimeoutError):
            return None
        finally:
            process.kill()
            process.wait(timeout=2)


def parse_uci(lines: list[str]) -> EngineResult | None:
    best_depth = -1
    by_pv: dict[int, tuple[int, list[str]]] = {}
    bestmove = None
    for raw in lines:
        line = raw.strip()
        if line.startswith("bestmove"):
            parts = line.split()
            if len(parts) >= 2 and parts[1] != "(none)":
                bestmove = parts[1]
            continue
        if not line.startswith("info ") or " pv " not in line or " score " not in line:
            continue
        tokens = line.split()
        depth = _int_after(tokens, "depth")
        multipv = _int_after(tokens, "multipv") or 1
        if depth is None or depth < best_depth:
            continue
        if depth > best_depth:
            best_depth = depth
            by_pv = {}
        score = _score(tokens)
        pv_index = tokens.index("pv")
        moves = [token for token in tokens[pv_index + 1 :] if len(token) >= 4]
        if score is None or not moves:
            continue
        by_pv[multipv] = (score, moves)
    if not by_pv and bestmove is None:
        return None
    ordered = [by_pv[key] for key in sorted(by_pv)]
    evaluation = ordered[0][0] if ordered else 0
    uci = [item[1][0] for item in ordered][:3]
    if bestmove and (not uci or uci[0] != bestmove):
        uci.insert(0, bestmove)
        uci = uci[:3]
    if not uci:
        return None
    return EngineResult(evaluation_cp=evaluation, uci_moves=uci)


def _collect(lines: queue.Queue[str | None], timeout_s: float) -> list[str]:
    import time

    deadline = time.monotonic() + timeout_s
    collected: list[str] = []
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            item = lines.get(timeout=max(0.05, remaining))
        except queue.Empty:
            break
        if item is None:
            break
        collected.append(item)
        if item.startswith("bestmove"):
            break
    else:
        raise TimeoutError
    if not any(line.startswith("bestmove") for line in collected):
        raise TimeoutError
    return collected


def _int_after(tokens: list[str], key: str) -> int | None:
    if key not in tokens:
        return None
    index = tokens.index(key)
    if index + 1 >= len(tokens):
        return None
    try:
        return int(tokens[index + 1])
    except ValueError:
        return None


def _score(tokens: list[str]) -> int | None:
    if "score" not in tokens:
        return None
    index = tokens.index("score")
    if index + 2 >= len(tokens):
        return None
    kind, raw = tokens[index + 1], tokens[index + 2]
    try:
        value = int(raw)
    except ValueError:
        return None
    if kind == "cp":
        return value
    if kind == "mate":
        if value > 0:
            return 100000 - value
        if value < 0:
            return -100000 - value
        return 0
    return None
