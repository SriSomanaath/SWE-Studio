"""Thin wrapper around litellm for provider portability.

Tests monkeypatch :func:`chat` directly so the loop can be exercised without
network access — see :mod:`tests.test_phase14`.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


RATE_LIMIT_RETRIES = 6  # 10+20+40+60+60+60 s: rides out a per-minute window several times


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # Prompt tokens served from the provider's cache (subset of prompt_tokens).
    cached_tokens: int = 0
    cost_usd: float = 0.0
    # Native tool calls: [{"id", "name", "arguments" (JSON string)}].
    tool_calls: list[dict] = field(default_factory=list)
    # Thinking models (Kimi K3) return their reasoning separately; it's sent
    # back with the assistant turn so multi-step tool use keeps its context.
    reasoning: str | None = None


def chat(
    *,
    messages: list[dict[str, Any]],
    model: str,
    api_key: str | None = None,
    # 4096, not 1024: a `write` call carries a whole file, and a call cut off
    # mid-JSON is unusable. Only generated tokens are billed.
    max_tokens: int = 4096,
    temperature: float = 0.2,
    tools: list[dict] | None = None,
) -> LLMResult:
    """Single LLM round-trip. Raises if litellm isn't installed."""
    try:
        from litellm import (  # type: ignore[import-not-found]
            RateLimitError,
            completion,
            completion_cost,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Agent mode requires litellm. Install with `pip install -e .[agent]` "
            f"or `pip install litellm`. Import failed with: {exc}"
        ) from exc

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        # litellm backs off on 429/5xx itself. Low-tier keys (e.g. Moonshot
        # at 3 RPM) otherwise kill a run mid-trajectory.
        "num_retries": 5,
        # Prompt caching. The agent resends its whole, growing history every
        # step, so nearly all input tokens repeat the previous call. litellm
        # sets two Anthropic cache breakpoints, the system prompt and the
        # latest turn; each step then reads the previous prefix at ~10% of the
        # input price and only pays full price (+25% write) for the new tail.
        # It stands down for non-Claude models, which need no markers: Moonshot
        # caches repeated prefixes automatically (measured 3072/3109 prompt
        # tokens cached on a repeat call, cost -88%), and vLLM reuses KV-cache
        # blocks for shared prefixes (automatic prefix caching).
        "enable_prompt_caching": True,
    }
    if tools:
        kwargs["tools"] = tools
    if model.startswith("hosted_vllm/"):
        # Self-hosted vLLM speaks the OpenAI API; litellm's hosted_vllm
        # provider handles it, we only point it at the in-cluster Service.
        # Its price is unknown to litellm, so cost_usd is 0: GPU spend is
        # measured per node-hour instead (scripts/bench_swebench.py).
        kwargs["api_base"] = os.environ.get("VLLM_BASE_URL", "http://vllm.swe-studio.svc:8000/v1")
    elif api_key:
        kwargs["api_key"] = api_key

    # litellm's num_retries backs off for seconds; per-minute quotas (Moonshot
    # tier 0 = 3 RPM shared by every parallel Job) need up to a minute. A 429
    # mid-run would otherwise throw away all the steps already paid for.
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            response = completion(**kwargs)
            break
        except RateLimitError:
            if attempt == RATE_LIMIT_RETRIES:
                raise
            delay = min(60, 10 * 2**attempt)
            logger.warning("rate limited by %s, retrying in %ss", model, delay)
            time.sleep(delay)
    message = response.choices[0].message
    text = message.content or ""
    tool_calls = [
        {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments or "{}"}
        for tc in (message.tool_calls or [])
    ]
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    # litellm normalises Anthropic cache_read_input_tokens and OpenAI-style
    # cached_tokens into prompt_tokens_details.cached_tokens.
    details = getattr(usage, "prompt_tokens_details", None) if usage else None
    cached_tokens = getattr(details, "cached_tokens", 0) or 0
    try:
        cost = float(completion_cost(completion_response=response))
    except Exception:  # noqa: BLE001
        cost = 0.0
    return LLMResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost_usd=cost,
        tool_calls=tool_calls,
        reasoning=getattr(message, "reasoning_content", None),
    )
