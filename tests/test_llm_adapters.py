"""Provider-agnostic LLM adapters (charter 2026-07-08: open-source models
behind the same seam — OpenAI-compatible servers like vLLM/Ollama/OpenRouter).

The HTTP surface is exercised against an httpx.MockTransport, so these tests
verify the real request/response handling without any network.
"""

import json

import httpx
import pytest

from app.platform.llm import adapter as adapter_module
from app.platform.llm import budget as budget_module
from app.platform.llm.adapter import (
    AnthropicAdapter,
    LLMNotConfiguredError,
    OpenAICompatibleAdapter,
    get_llm_adapter,
)
from app.platform.llm.budget import cost_for
from app.platform.settings.config import Settings

CHAT_COMPLETION = {
    "model": "llama-3.1-8b-instruct",
    "choices": [{"message": {"role": "assistant", "content": "scored"}}],
    "usage": {"prompt_tokens": 500, "completion_tokens": 60},
}


def make_adapter(handler, api_key="test-key"):
    return OpenAICompatibleAdapter(
        "http://llm.local/v1/",
        api_key,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_openai_compatible_request_and_response_shape() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=CHAT_COMPLETION)

    result = make_adapter(handler).complete(
        model="llama-3.1-8b-instruct", system="be a judge", user_content="the work", max_tokens=64
    )

    # Trailing slash normalized; auth and payload as the OpenAI API expects.
    assert captured["url"] == "http://llm.local/v1/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    assert captured["body"]["model"] == "llama-3.1-8b-instruct"
    assert captured["body"]["max_tokens"] == 64
    assert captured["body"]["messages"] == [
        {"role": "system", "content": "be a judge"},
        {"role": "user", "content": "the work"},
    ]
    assert result.text == "scored"
    assert result.model == "llama-3.1-8b-instruct"
    assert (result.input_tokens, result.output_tokens) == (500, 60)


def test_openai_compatible_no_auth_header_without_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers  # local Ollama needs no auth
        return httpx.Response(200, json=CHAT_COMPLETION)

    make_adapter(handler, api_key="").complete(
        model="m", system="s", user_content="u", max_tokens=8
    )


def test_openai_compatible_http_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(httpx.HTTPStatusError):
        # The executor/judge catch this and degrade — the adapter just raises.
        make_adapter(handler).complete(model="m", system="s", user_content="u", max_tokens=8)


def test_openai_compatible_requires_base_url() -> None:
    with pytest.raises(LLMNotConfiguredError):
        OpenAICompatibleAdapter("")


def test_factory_selects_provider_per_role(monkeypatch) -> None:
    settings = Settings(
        anthropic_api_key="sk-test",
        llm_judge_provider="openai_compatible",
        llm_judge_base_url="http://llm.local/v1",
    )
    monkeypatch.setattr(adapter_module, "get_settings", lambda: settings)

    assert isinstance(get_llm_adapter("judge"), OpenAICompatibleAdapter)
    assert isinstance(get_llm_adapter("executor"), AnthropicAdapter)


def test_factory_rejects_unknown_provider(monkeypatch) -> None:
    settings = Settings(llm_executor_provider="mystery-cloud")
    monkeypatch.setattr(adapter_module, "get_settings", lambda: settings)

    with pytest.raises(LLMNotConfiguredError):
        get_llm_adapter("executor")


def test_cost_uses_extra_price_overrides(monkeypatch) -> None:
    settings = Settings(llm_extra_model_prices={"llama-3.1": (0, 0), "qwen": (0.2, 0.2)})
    monkeypatch.setattr(budget_module, "get_settings", lambda: settings)

    assert cost_for("llama-3.1-8b-instruct", 1_000_000, 1_000_000) == 0.0
    assert cost_for("qwen-2.5-7b", 1_000_000, 1_000_000) == pytest.approx(0.4)
    # Anthropic prices and the fail-closed fallback are untouched.
    assert cost_for("claude-haiku-4-5", 1_000_000, 0) == pytest.approx(1.0)
    assert cost_for("mystery-model", 1_000_000, 1_000_000) == pytest.approx(60.0)
