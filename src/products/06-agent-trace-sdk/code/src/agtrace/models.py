"""Pydantic models for agent traces.

The schema in this file is the public API. Trace dashboards, exporters,
and incident tooling read this shape. Treat changes as breaking.
Versioned via `Trace.schema_version`.

Span shape borrows directly from OpenTelemetry:
  - `trace_id` groups all spans of one logical request
  - `span_id` uniquely identifies one span
  - `parent_span_id` builds the tree
  - timestamps in ISO-8601 / micro-second precision

We add a `kind` field tuned for AI agents (prompt / tool_call / retry /
agent / unknown). Generic OTel keeps a similar 'kind' (server / client
/ ... ) but ours is purpose-built.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.0.1"


# ---------------------------------------------------------------------------
# Spans + events
# ---------------------------------------------------------------------------

SpanKind = Literal[
    "agent",  # one full agent run (root of a trace, usually)
    "prompt",  # one LLM call -- system + user messages, model, output
    "tool_call",  # one tool / function the agent invoked
    "retry",  # explicit retry of a failed inner span
    "fallback",  # explicit fallback to a different model / tool
    "unknown",
]


SpanStatus = Literal["ok", "error", "cancelled"]


class SpanEvent(BaseModel):
    """A point-in-time event recorded inside a span (e.g. 'rate-limited')."""

    model_config = ConfigDict(frozen=True)

    name: str
    timestamp: datetime
    attributes: dict[str, str] = Field(default_factory=dict)


class Span(BaseModel):
    """One unit of work in a trace."""

    model_config = ConfigDict(frozen=False)

    trace_id: str = Field(..., description="Hex string identifying the trace.")
    span_id: str = Field(..., description="Hex string identifying this span.")
    parent_span_id: str | None = Field(
        default=None,
        description="Hex string of the parent span, or None for root spans.",
    )

    name: str = Field(..., description="Human-readable span name.")
    kind: SpanKind = "unknown"

    start_time: datetime
    end_time: datetime | None = None

    status: SpanStatus = "ok"
    status_message: str | None = None

    attributes: dict[str, str] = Field(default_factory=dict)
    events: list[SpanEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Trace aggregate
# ---------------------------------------------------------------------------


class Trace(BaseModel):
    """A full trace -- all spans for one logical request, in tree order."""

    model_config = ConfigDict(frozen=False)

    schema_version: str = SCHEMA_VERSION
    trace_id: str
    spans: list[Span] = Field(default_factory=list)

    @property
    def total_spans(self) -> int:
        return len(self.spans)

    @property
    def root(self) -> Span | None:
        for span in self.spans:
            if span.parent_span_id is None:
                return span
        return None
