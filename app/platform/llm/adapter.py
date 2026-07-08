"""Provider-agnostic LLM adapter seam (spec §28.7; charter 2026-07-08).

The platform talks to models only through :class:`LLMAdapter`, so the executor
and judges never know which provider is behind them. AnthropicAdapter is the
first implementation (Opus drafts, Haiku judges); an OpenAI-compatible adapter
for open-source judges (vLLM/Ollama) can be added here later without touching
any caller.

Tests (and any future provider swap) override the factory with
``set_llm_adapter(fake)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.platform.settings.config import get_settings


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMAdapter(Protocol):
    def complete(self, *, model: str, system: str, user_content: str, max_tokens: int) -> LLMResult:
        """Run one completion and return the text plus true token usage."""
        ...


class LLMNotConfiguredError(RuntimeError):
    """Raised when agent execution is attempted without an API key configured."""


# Models where adaptive thinking is the correct (and only) thinking config.
_ADAPTIVE_THINKING_PREFIXES = ("claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5")


class AnthropicAdapter:
    """Claude API implementation. Lazily constructs the client so the platform
    boots fine without a key — agent execution then degrades to manual."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise LLMNotConfiguredError(
                "ICM_ANTHROPIC_API_KEY is not set; agent execution is disabled"
            )
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, *, model: str, system: str, user_content: str, max_tokens: int) -> LLMResult:
        kwargs: dict = {}
        if model.startswith(_ADAPTIVE_THINKING_PREFIXES):
            kwargs["thinking"] = {"type": "adaptive"}
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
            **kwargs,
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResult(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


_override: LLMAdapter | None = None


def set_llm_adapter(adapter: LLMAdapter | None) -> None:
    """Install an adapter override (tests, future providers). None resets."""
    global _override
    _override = adapter


def get_llm_adapter() -> LLMAdapter:
    if _override is not None:
        return _override
    return AnthropicAdapter(get_settings().anthropic_api_key)
