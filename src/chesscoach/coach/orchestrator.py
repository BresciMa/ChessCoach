"""Uma chamada ao modelo por lance, por dica ou por mensagem. Nunca por quadro."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from chesscoach.analysis.facts import CoachFacts
from chesscoach.coach.policy import HelpPolicy, PolicyDecision, StockHelpPolicy, is_hint_request
from chesscoach.llm.gemini import LlmConnectionError, MissingApiKey, api_key_present
from chesscoach.llm.provider import LlmProvider
from chesscoach.messages import LEVEL_LABELS, MSG_LLM_FAILED, MSG_NO_ENGINE, MSG_NO_KEY, PIECE_RULES
from chesscoach.types import Level, Message, Reason

_SYSTEM = (
    "Você é o Chess Coach, um treinador de xadrez. Fale em português, com frases curtas, "
    "claras para adolescente e adulto. Use somente os fatos recebidos. "
    "Se best_move_san estiver ausente, não nomeie lance nem casa de destino de uma jogada sugerida. "
    "Não invente avaliação numérica."
)

_LEVEL_TONE = {
    Level.BEGINNER: "A pessoa está aprendendo o movimento das peças. Explique a peça que andou e, se houver best_move_san, indique esse único lance.",
    Level.LEVEL_1: "A pessoa sabe o básico. Sugira o próximo lance com base em best_move_san.",
    Level.LEVEL_2: "Alerte xeque, peça solta, ameaça ou rei no centro. Sem best_move_san, não diga o que jogar.",
    Level.LEVEL_3: "Fale de plano, desenvolvimento e segurança do rei. Sem best_move_san, não liste lances.",
    Level.MASTER: "Comente só o lance que já aconteceu e se a posição melhorou ou piorou. Sem best_move_san, não sugira o próximo.",
}


@dataclass
class Turn:
    decision: PolicyDecision
    text: str | None
    called_llm: bool


class CoachOrchestrator:
    def __init__(self, policy: HelpPolicy, llm: LlmProvider, model: str):
        self.policy = policy
        self.llm = llm
        self.model = model

    def respond(
        self,
        facts: CoachFacts,
        level: Level,
        reason: Reason,
        user_text: str | None = None,
    ) -> Turn:
        decision = self.policy.apply(facts, level, reason)
        if reason == Reason.MOVE_CONFIRMED and not decision.speak:
            return Turn(decision, None, False)
        if _engine_missing(facts) and level != Level.BEGINNER:
            return Turn(decision, MSG_NO_ENGINE, False)
        if level == Level.BEGINNER and not api_key_present() and reason == Reason.MOVE_CONFIRMED:
            return Turn(decision, _beginner_fallback(decision.facts_for_model), False)
        if not api_key_present():
            return Turn(decision, MSG_NO_KEY, False)
        messages = build_messages(decision, level, reason, user_text)
        try:
            text = self.llm.complete(messages, self.model)
        except MissingApiKey:
            return Turn(decision, MSG_NO_KEY, False)
        except LlmConnectionError as exc:
            return Turn(decision, str(exc), False)
        except Exception:
            return Turn(decision, MSG_LLM_FAILED, False)
        return Turn(decision, text, True)


def build_messages(
    decision: PolicyDecision,
    level: Level,
    reason: Reason,
    user_text: str | None,
) -> list[Message]:
    payload = json.dumps(asdict(decision.facts_for_model), ensure_ascii=False)
    band = decision.eval_band or ""
    ask = user_text.strip() if user_text else _default_ask(reason)
    user = (
        f"Nível: {LEVEL_LABELS[level]}. Motivo: {reason.value}. "
        f"Faixa: {band}. Pedido: {ask}\n{payload}"
    )
    system = _SYSTEM + " " + _LEVEL_TONE[level]
    return [Message("system", system), Message("user", user)]


def chat_reason(text: str) -> Reason:
    if is_hint_request(text):
        return Reason.HINT_REQUESTED
    return Reason.CHAT_MESSAGE


def _engine_missing(facts: CoachFacts) -> bool:
    return facts.evaluation_cp is None and facts.best_move_san is None


def _beginner_fallback(facts: CoachFacts) -> str:
    parts = [part for part in (facts.moved_piece, facts.moved_piece_rule) if part]
    if facts.best_move_san:
        parts.append(f"Uma ideia é {facts.best_move_san}.")
    if parts:
        return " ".join(parts)
    return PIECE_RULES["P"]


def _default_ask(reason: Reason) -> str:
    if reason == Reason.HINT_REQUESTED:
        return "A pessoa pediu um lance."
    if reason == Reason.CHAT_MESSAGE:
        return "Responda a mensagem."
    return "O adversário acabou de jogar. É a vez de quem usa o app. Comente este momento."
