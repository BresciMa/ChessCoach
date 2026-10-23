"""Fatos objetivos da posição. Não escreve texto para a pessoa."""

from __future__ import annotations

import chess

from chesscoach.analysis.facts import CoachFacts, KingFacts
from chesscoach.chess.game import ChessGame
from chesscoach.engine.uci import EngineResult
from chesscoach.messages import PIECE_NAMES, PIECE_RULES

_MINOR_START = {
    chess.WHITE: {chess.B1, chess.G1, chess.C1, chess.F1},
    chess.BLACK: {chess.B8, chess.G8, chess.C8, chess.F8},
}


class PositionAnalyzer:
    def analyze(
        self,
        game: ChessGame,
        engine: EngineResult | None,
        previous_evaluation_cp: int | None,
    ) -> CoachFacts:
        board = game.board
        side = "white" if board.turn == chess.WHITE else "black"
        hanging, threatened = _attacks(board)
        last_san, moved_piece, moved_rule = _last_move(board, game.sans)
        best, candidates = _engine_sans(board, engine)
        evaluation = engine.evaluation_cp if engine is not None else None
        return CoachFacts(
            fen=board.fen(),
            side_to_move=side,
            last_move_san=last_san,
            in_check=board.is_check(),
            moved_piece=moved_piece,
            moved_piece_rule=moved_rule,
            evaluation_cp=evaluation,
            previous_evaluation_cp=previous_evaluation_cp if evaluation is not None else previous_evaluation_cp,
            best_move_san=best,
            candidate_moves_san=candidates,
            hanging_squares=hanging,
            threatened_squares=threatened,
            development_white=_development(board, chess.WHITE),
            development_black=_development(board, chess.BLACK),
            own_king=_king(board, board.turn, game.history_known),
            opponent_king=_king(board, not board.turn, game.history_known),
        )


def _attacks(board: chess.Board) -> tuple[list[str], list[str]]:
    enemy = not board.turn
    hanging: list[str] = []
    threatened: list[str] = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != board.turn:
            continue
        if not board.is_attacked_by(enemy, square):
            continue
        name = chess.square_name(square)
        threatened.append(name)
        if not board.is_attacked_by(board.turn, square):
            hanging.append(name)
    hanging.sort()
    threatened.sort()
    return hanging, threatened


def _development(board: chess.Board, color: chess.Color) -> int:
    starts = _MINOR_START[color]
    count = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP):
        for square in board.pieces(piece_type, color):
            if square not in starts:
                count += 1
    return min(count, 4)


def _king(board: chess.Board, color: chess.Color, history_known: bool) -> KingFacts:
    square = board.king(color)
    start = chess.E1 if color == chess.WHITE else chess.E8
    if color == chess.WHITE:
        kingside = bool(board.castling_rights & chess.BB_H1)
        queenside = bool(board.castling_rights & chess.BB_A1)
    else:
        kingside = bool(board.castling_rights & chess.BB_H8)
        queenside = bool(board.castling_rights & chess.BB_A8)
    return KingFacts(
        on_start_square=square == start,
        kingside_rights=kingside,
        queenside_rights=queenside,
        castled=_castled(board, color) if history_known else None,
    )


def _castled(board: chess.Board, color: chess.Color) -> bool:
    start = chess.E1 if color == chess.WHITE else chess.E8
    start_file = chess.square_file(start)
    for move in board.move_stack:
        if move.from_square == start and abs(chess.square_file(move.to_square) - start_file) == 2:
            return True
    return False


def _last_move(board: chess.Board, sans: list[str]) -> tuple[str | None, str | None, str | None]:
    if not board.move_stack:
        return None, None, None
    move = board.move_stack[-1]
    san = sans[-1] if sans else None
    probe = board.copy()
    probe.pop()
    piece = probe.piece_at(move.from_square)
    if piece is None:
        return san, None, None
    symbol = piece.symbol()
    rule = PIECE_RULES[symbol.upper()]
    return san, PIECE_NAMES[symbol], rule


def _engine_sans(board: chess.Board, engine: EngineResult | None) -> tuple[str | None, list[str]]:
    if engine is None:
        return None, []
    found: list[str] = []
    for uci in engine.uci_moves[:3]:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            continue
        if move not in board.legal_moves:
            continue
        san = board.san(move)
        if san not in found:
            found.append(san)
    if not found:
        return None, []
    return found[0], found
