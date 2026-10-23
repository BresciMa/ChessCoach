"""Partida legal e o casamento entre casas que mudaram e um lance."""

from __future__ import annotations

from dataclasses import dataclass

import chess

from chesscoach.types import TrackerKind


@dataclass
class MoveMatch:
    kind: TrackerKind
    move: chess.Move | None = None
    origin: str | None = None
    destination: str | None = None


class ChessGame:
    def __init__(self, board: chess.Board | None = None, history_known: bool = True):
        self.board = board.copy() if board is not None else chess.Board()
        self.history_known = history_known
        self.sans: list[str] = []

    def reset(self) -> None:
        self.board = chess.Board()
        self.history_known = True
        self.sans.clear()

    def load_fen(self, fen: str, history_known: bool) -> None:
        self.board = chess.Board(fen)
        self.history_known = history_known
        self.sans.clear()

    @property
    def fen(self) -> str:
        return self.board.fen()

    def apply(self, move: chess.Move) -> str:
        san = self.board.san(move)
        self.board.push(move)
        self.sans.append(san)
        return san

    def parse_san(self, text: str) -> chess.Move | None:
        try:
            return self.board.parse_san(text.strip())
        except ValueError:
            return None


def match_legal_move(board: chess.Board, changed: set[str]) -> MoveMatch:
    """Escolhe o lance legal cujas casas cabem nas que mudaram.

    Se vários cabem, fica o que explica mais casas (roque e en passant
    ganham do passo curto do rei). Empate no tamanho é ambíguo.
    Promoções do mesmo origem-destino pedem a peça.
    """
    if not changed:
        return MoveMatch(TrackerKind.NO_CHANGE)
    groups: dict[tuple[int, int], list[chess.Move]] = {}
    for move in board.legal_moves:
        squares = affected_squares(board, move)
        if squares <= changed:
            groups.setdefault((move.from_square, move.to_square), []).append(move)
    if not groups:
        return MoveMatch(TrackerKind.NO_CHANGE)
    scored = []
    for moves in groups.values():
        size = len(affected_squares(board, moves[0]))
        scored.append((size, moves))
    best_size = max(item[0] for item in scored)
    best = [moves for size, moves in scored if size == best_size]
    if len(best) > 1:
        return MoveMatch(TrackerKind.AMBIGUOUS)
    chosen = best[0]
    sample = chosen[0]
    if any(move.promotion for move in chosen):
        return MoveMatch(
            TrackerKind.PROMOTION_NEEDED,
            origin=chess.square_name(sample.from_square),
            destination=chess.square_name(sample.to_square),
        )
    return MoveMatch(TrackerKind.MOVE_CONFIRMED, move=sample)


def shortest_replays(board: chess.Board, placement: dict[str, str], max_plies: int = 4) -> list[list[chess.Move]]:
    """Sequências legais mais curtas que chegam nesta disposição de peças.

    O caminho vazio significa que as peças já são as mesmas. Lista vazia
    significa que não há caminho dentro do limite.
    """
    target = dict(placement)
    target_key = _placement_key(target)
    if _board_key(board) == target_key:
        return [[]]
    found: list[list[chess.Move]] = []
    queue: list[tuple[chess.Board, list[chess.Move]]] = [(board.copy(), [])]
    seen = {board.epd()}
    while queue:
        current, moves = queue.pop(0)
        if found and len(moves) >= len(found[0]):
            continue
        if len(moves) >= max_plies:
            continue
        diff = _diff_squares(current, target)
        for move in current.legal_moves:
            if move.from_square not in diff and move.to_square not in diff:
                continue
            nxt = current.copy()
            nxt.push(move)
            key = nxt.epd()
            if key in seen:
                continue
            seen.add(key)
            path = [*moves, move]
            if _board_key(nxt) == target_key:
                if found and len(path) > len(found[0]):
                    return found
                found.append(path)
            elif not found:
                queue.append((nxt, path))
    return found


def _placement_key(placement: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(placement.items()))


def _board_key(board: chess.Board) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((chess.square_name(square), piece.symbol()) for square, piece in board.piece_map().items()))


def _diff_squares(board: chess.Board, target: dict[str, str]) -> set[int]:
    current = {chess.square_name(square): piece.symbol() for square, piece in board.piece_map().items()}
    names = set(current) | set(target)
    return {chess.parse_square(name) for name in names if current.get(name) != target.get(name)}


def affected_squares(board: chess.Board, move: chess.Move) -> set[str]:
    squares = {move.from_square, move.to_square}
    if board.is_en_passant(move):
        squares.add(chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square)))
    if board.is_castling(move):
        rank = chess.square_rank(move.from_square)
        if chess.square_file(move.to_square) == 6:
            squares.add(chess.square(7, rank))
            squares.add(chess.square(5, rank))
        else:
            squares.add(chess.square(0, rank))
            squares.add(chess.square(3, rank))
    return {chess.square_name(square) for square in squares}
