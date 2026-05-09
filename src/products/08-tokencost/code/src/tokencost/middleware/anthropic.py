"""TokenCost middleware for the Anthropic Python SDK.

Wraps an `anthropic.Anthropic` client so every successful call to
`client.messages.create(...)` gets recorded as a `TokenUsage` event.

Usage:

    from anthropic import Anthropic
    from tokencost.middleware.anthropic import wrap

    client = wrap(
        Anthropic(),
        feature="pr-review",
        environment="prod",
    )
    response = client.messages.create(model="claude-sonnet-4-6", ...)

The wrapper is a thin proxy: any attribute / method you didn't
intercept passes through to the real client unchanged. We import the
SDK lazily inside the test path so tokencost installs without
`anthropic` as a required dep.
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


class _WrappedMessages:
    """Proxy for `client.messages` that intercepts `.create(...)`."""

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
            # Recording failures must NEVER break the user's request.
            logger.warning("tokencost recording failed: %s", exc)
            if self._on_error is not None:
                self._on_error(exc)
        return response

    def _record(self, response: Any) -> None:
        """Extract usage off an Anthropic Message and emit a TokenUsage."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        if input_tokens == 0 and output_tokens == 0:
            return  # nothing to bill -- e.g. tool_use without text generation

        model = getattr(response, "model", "") or ""
        provider = "anthropic"

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
        # Anything we don't intercept (.list(), .stream(), etc.) passes through.
        return getattr(self._real, item)


class _WrappedAnthropicClient:
    """Tiny proxy that swaps `.messages` for the recorded version."""

    def __init__(
        self,
        real: Any,
        *,
        defaults: dict[str, str | None],
        sink: Sink,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._real = real
        self.messages = _WrappedMessages(
            real.messages,
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
    """Return a tokencost-instrumented proxy for an Anthropic client.

    Parameters that are not None become wrap-time defaults; the
    `tokencost.attribution` context manager can override them per-call.
    """
    if not hasattr(client, "messages"):
        raise TypeError(
            "wrap() expected an Anthropic-shaped client (with `.messages`); "
            f"got {type(client).__name__}"
        )
    return _WrappedAnthropicClient(
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
    """Pull the message id off the response if it exposes one."""
    val = getattr(response, "id", None)
    return val if isinstance(val, str) else None
