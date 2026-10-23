from pathlib import Path

from chesscoach.engine.uci import StockfishEngine, parse_uci


def test_parser_reads_score_and_up_to_three_moves():
    lines = [
        "info depth 10 multipv 1 score cp 34 pv e2e4 e7e5 g1f3",
        "info depth 10 multipv 2 score cp 20 pv d2d4 d7d5",
        "info depth 10 multipv 3 score cp 12 pv g1f3",
        "info depth 8 multipv 1 score cp 1 pv a2a3",
        "bestmove e2e4",
    ]
    result = parse_uci(lines)
    assert result is not None
    assert result.evaluation_cp == 34
    assert result.uci_moves == ["e2e4", "d2d4", "g1f3"]


def test_missing_binary_returns_none_without_raising(tmp_path):
    missing = tmp_path / "stockfish-ausente.exe"
    engine = StockfishEngine(str(missing), movetime_ms=50)
    assert engine.analyze(chess_start()) is None
    assert engine.analyze("8/8/8/8/8/8/8/4K2k w - - 0 1") is None


def test_real_stockfish_when_present():
    path = _find_stockfish()
    if path is None:
        return
    engine = StockfishEngine(str(path), movetime_ms=80)
    result = engine.analyze(chess_start())
    assert result is not None
    assert result.best_move


def chess_start() -> str:
    return "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _find_stockfish() -> Path | None:
    import os
    import shutil

    found = shutil.which("stockfish")
    if found:
        return Path(found)
    for candidate in (
        Path(os.environ.get("STOCKFISH_PATH", "")),
        Path(r"C:\Program Files\stockfish\stockfish.exe"),
    ):
        if candidate.is_file():
            return candidate
    return None
