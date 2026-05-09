"""SDK middlewares: one-line wrappers that auto-record TokenUsage.

This package provides:

  - `Sink`                    callable type every backend implements
  - `default_sink(path)`      JSONL-appender sink (the default backend)
  - `chain(*sinks)`           composes multiple sinks; one failure
                              never stops later sinks from running
  - `to_active_agtrace_span()` cross-product integration: attaches
                              cost / token / model attributes to the
                              currently-active `agtrace` span when
                              tokencost records a usage event

Provider-specific wrappers live in submodules:

    from tokencost.middleware.anthropic import wrap as wrap_anthropic
    from tokencost.middleware.openai    import wrap as wrap_openai
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from tokencost import store
from tokencost.models import MICROS_PER_USD, TokenUsage

logger = logging.getLogger(__name__)

# A sink is a callable that consumes a TokenUsage. Any callable works:
# a function, a method, a closure, a queue producer.
Sink = Callable[[TokenUsage], None]


def default_sink(path: Path | None = None) -> Sink:
    """Return a sink that appends each event to a JSONL file."""
    target = path or Path(".tokencost/usage.jsonl")

    def _sink(usage: TokenUsage) -> None:
        store.append(target, usage)

    return _sink


def chain(*sinks: Sink) -> Sink:
    """Combine multiple sinks into one. Each runs even if a prior one raised.

    Use case: write to JSONL on disk **and** annotate the active
    agtrace span on every recording call.

        from tokencost.middleware import chain, default_sink, to_active_agtrace_span
        from tokencost.middleware.anthropic import wrap

        client = wrap(
            Anthropic(),
            sink=chain(default_sink(), to_active_agtrace_span()),
        )

    Failures in any individual sink are logged but do NOT prevent the
    remaining sinks from running. The chain itself never raises.
    """

    def _chained(usage: TokenUsage) -> None:
        for s in sinks:
            try:
                s(usage)
            except Exception:
                logger.exception("sink failed; continuing chain")

    return _chained


def to_active_agtrace_span() -> Sink:
    """Sink that pins cost / token attrs on the active agtrace span.

    When `agtrace` isn't installed, returns a no-op sink so this can
    always be safely added to a chain. When installed but no span is
    active, the call also no-ops -- no warning, no error.

    The attributes set on the span:

      tokens.input          str(input_tokens)
      tokens.output         str(output_tokens)
      tokens.total          str(input + output)
      cost.micros           str(cost_micros)
      cost.usd              "$X.XXXX"
      llm.provider          provider name
      llm.model             model name
    """

    try:
        from agtrace.tracer import attach_attributes
    except ImportError:
        # agtrace isn't installed in this environment. The sink is a
        # no-op but still has the same shape so chain() is happy.
        def _disabled(_usage: TokenUsage) -> None:
            return None

        return _disabled

    def _sink(usage: TokenUsage) -> None:
        attach_attributes(
            {
                "tokens.input": usage.input_tokens,
                "tokens.output": usage.output_tokens,
                "tokens.total": usage.input_tokens + usage.output_tokens,
                "cost.micros": usage.cost_micros,
                "cost.usd": f"${usage.cost_micros / MICROS_PER_USD:.4f}",
                "llm.provider": usage.provider,
                "llm.model": usage.model,
            }
        )

    return _sink


__all__ = [
    "Sink",
    "chain",
    "default_sink",
    "to_active_agtrace_span",
]
