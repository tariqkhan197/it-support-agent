"""
Groq LLM client wrapper.

Wraps langchain_groq.ChatGroq with:
    - retry with exponential backoff (transient network/5xx errors)
    - latency + token usage logging (logs/token_usage.log)
    - a minimal Protocol (`LLMClient`) so agents depend on an interface,
      not a concrete class — this lets tests inject a fake client without
      any network access or API key.
"""

import time
from typing import Protocol

from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config.settings import get_settings
from backend.utils.exceptions import LLMProviderError
from backend.utils.logger import get_logger, token_usage_logger

settings = get_settings()
logger = get_logger(__name__)


class LLMMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMResult(BaseModel):
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0


class LLMClient(Protocol):
    """Interface every agent codes against. GroqLLMClient and FakeLLMClient both satisfy it."""

    def invoke(self, messages: list[LLMMessage], *, agent_name: str | None = None) -> LLMResult: ...


class GroqLLMClient:
    """Production LLM client backed by Groq's free-tier Llama models."""

    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        self.model = model or settings.GROQ_MODEL
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self._chat = None  # lazily constructed — avoids requiring an API key at import time

    def _get_chat(self):
        if self._chat is None:
            if not settings.GROQ_API_KEY:
                raise LLMProviderError(
                    "GROQ_API_KEY is not configured. Set it in your .env file "
                    "(get a free key at https://console.groq.com)."
                )
            # Imported lazily so this module has no hard dependency at import time.
            from langchain_groq import ChatGroq

            self._chat = ChatGroq(
                model=self.model,
                temperature=self.temperature,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_REQUEST_TIMEOUT,
                api_key=settings.GROQ_API_KEY,
            )
        return self._chat

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(LLMProviderError),
    )
    def invoke(self, messages: list[LLMMessage], *, agent_name: str | None = None) -> LLMResult:
        chat = self._get_chat()
        start = time.perf_counter()

        try:
            lc_messages = [(m.role, m.content) for m in messages]
            response = chat.invoke(lc_messages)
        except Exception as exc:  # noqa: BLE001 — deliberately broad: wrap every provider failure
            raise LLMProviderError(f"Groq API call failed: {exc}") from exc

        latency_ms = (time.perf_counter() - start) * 1000

        usage = getattr(response, "usage_metadata", None) or {}
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        token_usage_logger.log(
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            agent=agent_name,
        )
        logger.info(
            "LLM call [%s] agent=%s latency=%.0fms tokens=%d",
            self.model, agent_name, latency_ms, total_tokens,
        )

        return LLMResult(
            content=response.content,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
        )
