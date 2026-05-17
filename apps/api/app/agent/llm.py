"""Thin wrapper around litellm for provider portability.

Tests monkeypatch :func:`chat` directly so the loop can be exercised without
network access — see :mod:`tests.test_phase14`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


def chat(
    *,
    messages: list[dict[str, Any]],
    model: str,
    api_key: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> LLMResult:
    """Single LLM round-trip. Raises if litellm isn't installed."""
    try:
        from litellm import completion, completion_cost  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Agent mode requires litellm. Install with `pip install -e .[agent]` "
            "or `pip install litellm`."
        ) from exc

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if api_key:
        kwargs["api_key"] = api_key

    response = completion(**kwargs)
    text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    try:
        cost = float(completion_cost(completion_response=response))
    except Exception:  # noqa: BLE001
        cost = 0.0
    return LLMResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost,
    )
