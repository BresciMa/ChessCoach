"""CoachFacts: contrato entre o analisador e a política. Não é um serviço."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KingFacts:
    on_start_square: bool
    kingside_rights: bool
    queenside_rights: bool
    castled: bool | None


@dataclass
class CoachFacts:
    fen: str
    side_to_move: str
    last_move_san: str | None
    in_check: bool
    moved_piece: str | None
    moved_piece_rule: str | None
    evaluation_cp: int | None
    previous_evaluation_cp: int | None
    best_move_san: str | None
    candidate_moves_san: list[str]
    hanging_squares: list[str]
    threatened_squares: list[str]
    development_white: int
    development_black: int
    own_king: KingFacts
    opponent_king: KingFacts
    best_move_plain: str | None = None
    last_move_plain: str | None = None
    previous_move_plain: str | None = None
    opening_name: str | None = None
    candidate_moves_plain: list[str] = field(default_factory=list)
    mate_on_next: bool = False
