"""Provider-agnostic LLM adapter seam (spec §28.7; charter 2026-07-08).

The platform talks to models only through :class:`LLMAdapter`, so the executor
and judges never know which provider is behind them. Two implementations:
AnthropicAdapter (Opus drafts, Haiku judges) and OpenAICompatibleAdapter
(open-source and third-party models via the OpenAI chat-completions API —
vLLM, Ollama, OpenRouter, Groq, Together). Each role picks its provider via
ICM_LLM_{EXECUTOR,JUDGE}_PROVIDER, so e.g. a free open-source judge can run
alongside a Claude executor; the calibration loop (judge-vs-human agreement,
auto-widen, drift) measures whether the cheaper judge holds up.

Tests (and any future provider swap) override the factory with
``set_llm_adapter(fake)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

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


class OpenAICompatibleAdapter:
    """Any server speaking the OpenAI chat-completions API: vLLM, Ollama,
    OpenRouter, Groq, Together. Uses httpx directly — the surface is one POST.
    api_key may be empty for local servers that need no auth."""

    _TIMEOUT_SECONDS = 300.0  # local models on modest hardware can be slow

    def __init__(
        self, base_url: str, api_key: str = "", *, http_client: httpx.Client | None = None
    ) -> None:
        if not base_url:
            raise LLMNotConfiguredError(
                "openai_compatible provider selected but no base_url configured "
                "(set ICM_LLM_EXECUTOR_BASE_URL / ICM_LLM_JUDGE_BASE_URL)"
            )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = http_client or httpx.Client(timeout=self._TIMEOUT_SECONDS)

    def complete(self, *, model: str, system: str, user_content: str, max_tokens: int) -> LLMResult:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        response = self._client.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"].get("content") or ""
        # Servers that omit usage bill zero tokens — acceptable for local/free
        # models; hosted ones all return it.
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
            model=data.get("model", model),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )


Purpose = Literal["executor", "judge"]

_override: LLMAdapter | None = None


def set_llm_adapter(adapter: LLMAdapter | None) -> None:
    """Install an adapter override (tests, future providers). None resets."""
    global _override
    _override = adapter


def get_llm_adapter(purpose: Purpose = "executor") -> LLMAdapter:
    """The adapter for a role, per ICM_LLM_{EXECUTOR,JUDGE}_PROVIDER."""
    if _override is not None:
        return _override
    settings = get_settings()
    if purpose == "judge":
        provider = settings.llm_judge_provider
        base_url, api_key = settings.llm_judge_base_url, settings.llm_judge_api_key
    else:
        provider = settings.llm_executor_provider
        base_url, api_key = settings.llm_executor_base_url, settings.llm_executor_api_key

    if provider == "openai_compatible":
        return OpenAICompatibleAdapter(base_url, api_key)
    if provider == "anthropic":
        return AnthropicAdapter(settings.anthropic_api_key)
    raise LLMNotConfiguredError(f"unknown LLM provider {provider!r} for {purpose}")
