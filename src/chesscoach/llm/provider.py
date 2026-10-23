"""Contrato do modelo de linguagem. A implementação padrão é o Gemini."""

from __future__ import annotations

from chesscoach.types import Message


class LlmProvider:
    def complete(self, messages: list[Message], model: str) -> str: ...
