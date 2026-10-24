"""Recorte do que cada nível pode ver. O Gemini não recebe o que foi apagado."""

from __future__ import annotations

from dataclasses import dataclass, replace

from chesscoach.analysis.facts import CoachFacts
from chesscoach.types import Level, Reason

CP_MILD = 150
CP_LARGE = 400

_HINT_PHRASES = (
    "qual lance",
    "o que jogar",
    "melhor jogada",
    "sugere",
    "sugira",
    "me dá uma dica",
    "me da uma dica",
)


class HelpPolicy:
    def apply(self, facts: CoachFacts, level: Level, reason: Reason) -> PolicyDecision: ...


@dataclass
class PolicyDecision:
    speak: bool
    facts_for_model: CoachFacts
    eval_band: str | None
    arrow: str | None
    threat_squares: list[str]


class StockHelpPolicy:
    def apply(self, facts: CoachFacts, level: Level, reason: Reason) -> PolicyDecision:
        packet = _clone(facts)
        arrow: str | None = None
        threats: list[str] = []
        hide_numbers = level in {Level.LEVEL_2, Level.LEVEL_3, Level.MASTER}
        if hide_numbers:
            packet = _hide_cp(packet)

        if reason == Reason.HINT_REQUESTED:
            packet.best_move_san = facts.best_move_san
            if level in {Level.BEGINNER, Level.MASTER}:
                packet.candidate_moves_san = []
            else:
                packet.candidate_moves_san = list(facts.candidate_moves_san)
            arrow = facts.best_move_san
            speak = True
            if level == Level.LEVEL_2:
                threats = _threats(facts)
        else:
            if level == Level.BEGINNER:
                packet.candidate_moves_san = []
                packet.candidate_moves_plain = []
            elif level != Level.LEVEL_1:
                packet = _hide_moves(packet)
            speak = True
            if level == Level.LEVEL_2 and reason == Reason.MOVE_CONFIRMED:
                speak = _has_alert(facts) or facts.mate_on_next
                threats = _threats(facts) if speak else []
            elif level == Level.LEVEL_2:
                threats = _threats(facts)
            if level == Level.LEVEL_1 and reason == Reason.MOVE_CONFIRMED:
                arrow = facts.best_move_san

        return PolicyDecision(
            speak=speak,
            facts_for_model=packet,
            eval_band=_band(facts, level, reason),
            arrow=arrow,
            threat_squares=threats,
        )


def is_hint_request(text: str) -> bool:
    folded = " ".join(text.casefold().split())
    if folded == "dica":
        return True
    return any(phrase in folded for phrase in _HINT_PHRASES if phrase != "dica")


def band_from_cp(cp: int) -> str:
    if cp >= CP_LARGE:
        return "vantagem grande"
    if cp >= CP_MILD:
        return "vantagem"
    if cp >= -CP_MILD:
        return "equilíbrio"
    if cp >= -CP_LARGE:
        return "desvantagem"
    return "desvantagem grande"


def _band(facts: CoachFacts, level: Level, reason: Reason) -> str | None:
    if facts.evaluation_cp is None:
        return None
    if (
        level == Level.MASTER
        and reason == Reason.MOVE_CONFIRMED
        and facts.previous_evaluation_cp is not None
    ):
        mover_is_white = facts.side_to_move == "black"
        delta = facts.evaluation_cp - facts.previous_evaluation_cp
        if not mover_is_white:
            delta = -delta
        return band_from_cp(delta)
    if level == Level.MASTER:
        cp = facts.evaluation_cp if facts.side_to_move == "white" else -facts.evaluation_cp
        return band_from_cp(cp)
    return band_from_cp(facts.evaluation_cp)


def _has_alert(facts: CoachFacts) -> bool:
    king_in_center = facts.own_king.on_start_square and facts.own_king.castled is not True
    return bool(facts.in_check or facts.hanging_squares or facts.threatened_squares or king_in_center)


def _threats(facts: CoachFacts) -> list[str]:
    seen: list[str] = []
    for square in facts.hanging_squares + facts.threatened_squares:
        if square not in seen:
            seen.append(square)
    return seen


def _hide_cp(facts: CoachFacts) -> CoachFacts:
    return replace(facts, evaluation_cp=None, previous_evaluation_cp=None)


def _hide_moves(facts: CoachFacts) -> CoachFacts:
    return replace(
        facts,
        best_move_san=None,
        best_move_plain=None,
        candidate_moves_san=[],
        candidate_moves_plain=[],
    )


def _clone(facts: CoachFacts) -> CoachFacts:
    return replace(
        facts,
        candidate_moves_san=list(facts.candidate_moves_san),
        candidate_moves_plain=list(facts.candidate_moves_plain),
        hanging_squares=list(facts.hanging_squares),
        threatened_squares=list(facts.threatened_squares),
        own_king=replace(facts.own_king),
        opponent_king=replace(facts.opponent_king),
    )
