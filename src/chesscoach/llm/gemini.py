"""Gemini atrás de LlmProvider. A chave só é lida aqui, e não é registrada."""

from __future__ import annotations

import os
import ssl

from chesscoach.messages import MSG_LLM_FAILED, MSG_SSL
from chesscoach.types import Message


class MissingApiKey(RuntimeError):
    pass


class LlmConnectionError(RuntimeError):
    pass


def api_key_present() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def gemini_ssl_context() -> ssl.SSLContext:
    """Confia no certificado da rede quando ele já está no Windows.

    O cliente do Gemini, sozinho, usa só o pacote certifi. Um proxy corporativo
    entra na cadeia com um certificado próprio e a chamada falha.
    """
    cafile = os.environ.get("SSL_CERT_FILE") or None
    capath = os.environ.get("SSL_CERT_DIR") or None
    if cafile or capath:
        return ssl.create_default_context(cafile=cafile, capath=capath)
    try:
        import truststore
    except ImportError:
        return ssl.create_default_context()
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class GeminiProvider:
    def complete(self, messages: list[Message], model: str) -> str:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise MissingApiKey
        from google import genai

        system = "\n".join(item.content for item in messages if item.role == "system")
        dialogue = [item.content for item in messages if item.role != "system"]
        user = "\n\n".join(dialogue)
        context = gemini_ssl_context()
        client = genai.Client(
            api_key=key,
            http_options={
                "client_args": {"verify": context},
                "async_client_args": {"verify": context},
            },
        )
        try:
            response = client.models.generate_content(
                model=model,
                contents=user,
                config={"system_instruction": system} if system else None,
            )
        except Exception as exc:
            if _ssl_failure(exc):
                raise LlmConnectionError(MSG_SSL) from exc
            raise LlmConnectionError(MSG_LLM_FAILED) from exc
        text = getattr(response, "text", None)
        if not text:
            raise LlmConnectionError("O modelo não devolveu texto.")
        return text.strip()


def _ssl_failure(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        text = str(current).lower()
        if "certificate" in text or "ssl" in text:
            return True
        current = current.__cause__ or current.__context__
    return False
