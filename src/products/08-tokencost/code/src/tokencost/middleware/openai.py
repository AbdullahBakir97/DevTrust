"""TokenCost middleware for the OpenAI Python SDK.

Wraps an `openai.OpenAI` client so every successful call to
`client.chat.completions.create(...)` (or
`client.responses.create(...)` on newer SDK versions) gets recorded
as a TokenUsage event.

Usage:

    from openai import OpenAI
    from tokencost.middleware.openai import wrap

    client = wrap(OpenAI(), feature="search", environment="prod")
    response = client.chat.completions.create(model="gpt-5", ...)

OpenAI's response object exposes `.usage.prompt_tokens` and
`.usage.completion_tokens` (or `.input_tokens` / `.output_tokens` on
the Responses API). We try both shapes for forward compatibility.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from tokencost.attribution import merged_with
from tokencost.middleware import Sink, default_sink
from tokencost.models import TokenUsage
from tokencost.prices import estimate_cost_micros

logger = logging.getLogger(__name__)


def _extract_usage_pair(usage_obj: Any) -> tuple[int, int]:
    """Return (input_tokens, output_tokens). Tries both SDK shapes."""
    if usage_obj is None:
        return (0, 0)
    # Chat-completions SDK shape
    prompt = getattr(usage_obj, "prompt_tokens", None)
    completion = getattr(usage_obj, "completion_tokens", None)
    if prompt is not None or completion is not None:
        return (int(prompt or 0), int(completion or 0))
    # Responses API shape
    in_tok = getattr(usage_obj, "input_tokens", None)
    out_tok = getattr(usage_obj, "output_tokens", None)
    return (int(in_tok or 0), int(out_tok or 0))


class _RecordingCreate:
    """Proxy that wraps a `.create(...)` method on a leaf endpoint."""

    def __init__(
        self,
        real: Any,
        *,
        defaults: dict[str, str | None],
        sink: Sink,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._real = real
        self._defaults = defaults
        self._sink = sink
        self._on_error = on_error

    def create(self, *args: Any, **kwargs: Any) -> Any:
        response = self._real.create(*args, **kwargs)
        try:
            self._record(response)
        except Exception as exc:
            logger.warning("tokencost recording failed: %s", exc)
            if self._on_error is not None:
                self._on_error(exc)
        return response

    def _record(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        input_tokens, output_tokens = _extract_usage_pair(usage)
        if input_tokens == 0 and output_tokens == 0:
            return

        model = getattr(response, "model", "") or ""
        provider = "openai"
        cost_micros = estimate_cost_micros(provider, model, input_tokens, output_tokens) or 0
        attrs = merged_with(self._defaults)
        request_id = attrs.get("request_id") or _safe_id(response)

        ev = TokenUsage(
            timestamp=datetime.now(UTC),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_micros=cost_micros,
            feature=attrs.get("feature"),
            environment=attrs.get("environment"),
            actor=attrs.get("actor"),
            request_id=request_id,
            status="ok",
        )
        self._sink(ev)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._real, item)


class _WrappedChat:
    """Proxy for `client.chat` that swaps `.completions`."""

    def __init__(
        self,
        real: Any,
        *,
        defaults: dict[str, str | None],
        sink: Sink,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._real = real
        self.completions = _RecordingCreate(
            real.completions,
            defaults=defaults,
            sink=sink,
            on_error=on_error,
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._real, item)


class _WrappedOpenAIClient:
    """Top-level proxy for an OpenAI client. Wraps both `.chat` and
    `.responses` if they exist."""

    def __init__(
        self,
        real: Any,
        *,
        defaults: dict[str, str | None],
        sink: Sink,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._real = real
        if hasattr(real, "chat"):
            self.chat = _WrappedChat(
                real.chat,
                defaults=defaults,
                sink=sink,
                on_error=on_error,
            )
        if hasattr(real, "responses"):
            # Responses API: client.responses.create(...)
            self.responses = _RecordingCreate(
                real.responses,
                defaults=defaults,
                sink=sink,
                on_error=on_error,
            )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._real, item)


def wrap(
    client: Any,
    *,
    feature: str | None = None,
    environment: str | None = None,
    actor: str | None = None,
    sink: Sink | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> Any:
    """Return a tokencost-instrumented proxy for an OpenAI client."""
    if not (hasattr(client, "chat") or hasattr(client, "responses")):
        raise TypeError(
            "wrap() expected an OpenAI-shaped client (with `.chat` or "
            f"`.responses`); got {type(client).__name__}"
        )
    return _WrappedOpenAIClient(
        client,
        defaults={
            "feature": feature,
            "environment": environment,
            "actor": actor,
        },
        sink=sink or default_sink(),
        on_error=on_error,
    )


def _safe_id(response: Any) -> str | None:
    val = getattr(response, "id", None)
    return val if isinstance(val, str) else None
