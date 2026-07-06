"""Thin LLM wrapper with cheap/strong model routing (doc section 4 stage-routing
rule). One provider (Anthropic) — swap the two `_call` bodies if you need another.
"""
from __future__ import annotations

import abc

from config.settings import MODEL_CHEAP, MODEL_STRONG
from contracts.types import LLMResponse


class LLMClient(abc.ABC):
    @abc.abstractmethod
    def call_cheap(self, system: str, user: str, max_tokens: int = 400) -> LLMResponse: ...

    @abc.abstractmethod
    def call_strong(self, system: str, user: str, max_tokens: int = 400) -> LLMResponse: ...


class AnthropicLLMClient(LLMClient):
    """Real client. Requires ANTHROPIC_API_KEY in the environment."""

    def __init__(self) -> None:
        import anthropic  # imported lazily so the stub client needs no dependency/key
        self._client = anthropic.Anthropic()

    def _call(self, model: str, system: str, user: str, max_tokens: int) -> LLMResponse:
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        return LLMResponse(
            text=text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            model=model,
        )

    def call_cheap(self, system: str, user: str, max_tokens: int = 400) -> LLMResponse:
        return self._call(MODEL_CHEAP, system, user, max_tokens)

    def call_strong(self, system: str, user: str, max_tokens: int = 400) -> LLMResponse:
        return self._call(MODEL_STRONG, system, user, max_tokens)


class StubLLMClient(LLMClient):
    """Deterministic, network-free client for tests and for running the pipeline
    without an API key. Returns canned responses keyed by substring match on the
    user prompt, falling through to a default per call kind."""

    def __init__(self, cheap_responses: dict[str, str] | None = None,
                 strong_responses: dict[str, str] | None = None,
                 default_cheap: str = "OK", default_strong: str = "SELECT 1"):
        self.cheap_responses = cheap_responses or {}
        self.strong_responses = strong_responses or {}
        self.default_cheap = default_cheap
        self.default_strong = default_strong
        self.calls: list[tuple[str, str, str]] = []  # (kind, system, user)

    def _match(self, table: dict[str, str], user: str, default: str) -> str:
        for k, v in table.items():
            if k in user:
                return v
        return default

    def call_cheap(self, system: str, user: str, max_tokens: int = 400) -> LLMResponse:
        self.calls.append(("cheap", system, user))
        text = self._match(self.cheap_responses, user, self.default_cheap)
        return LLMResponse(text=text, input_tokens=len(user) // 4, output_tokens=len(text) // 4, model="stub-cheap")

    def call_strong(self, system: str, user: str, max_tokens: int = 400) -> LLMResponse:
        self.calls.append(("strong", system, user))
        text = self._match(self.strong_responses, user, self.default_strong)
        return LLMResponse(text=text, input_tokens=len(user) // 4, output_tokens=len(text) // 4, model="stub-strong")


def get_llm_client() -> LLMClient:
    """Factory used by the orchestrator/API/UI. Falls back to the stub client
    when no API key is configured, so the pipeline is always runnable."""
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicLLMClient()
    return StubLLMClient()
