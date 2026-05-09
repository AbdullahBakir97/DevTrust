"""In-process tracer with span tree, exporters, and a context manager API.

Design:
  - `Tracer.span()` returns a `Span`-shaped object you can use as a
    context manager OR as a decorator. Entering starts the span;
    exiting ends it (and exports it via the configured exporter).
  - Spans are nested via a `ContextVar` so async + threads work.
  - Exporters consume spans one at a time. Default is the JSONL
    appender; operators swap in OTLP / Jaeger / their own callback.

We deliberately don't try to BE OpenTelemetry. The interest is in
agent-shaped data that OTel doesn't model well -- prompts, tool calls,
fallback edges. Once a project graduates to a full OTel collector, the
exporter swap is one line.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from agtrace.models import Span, SpanEvent, SpanKind, SpanStatus

logger = logging.getLogger(__name__)


SpanExporter = Callable[[Span], None]


# Active span (used to build parent chains automatically).
_current: ContextVar[SpanHandle | None] = ContextVar("agtrace_current_span", default=None)


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def _new_trace_id() -> str:
    """16 random bytes -> 32 hex chars. Matches OpenTelemetry's trace_id width."""
    return secrets.token_hex(16)


def _new_span_id() -> str:
    """8 random bytes -> 16 hex chars. Matches OpenTelemetry's span_id width."""
    return secrets.token_hex(8)


# ---------------------------------------------------------------------------
# Span handle (mutable while open, frozen on export)
# ---------------------------------------------------------------------------


class SpanHandle:
    """Mutable span surface returned by `Tracer.span()`.

    Apps set attributes / record events while the block is active. On
    exit we materialize an immutable `Span` and hand it to the exporter.
    """

    __slots__ = (
        "_attributes",
        "_end_time",
        "_events",
        "_kind",
        "_name",
        "_parent_span_id",
        "_span_id",
        "_start_time",
        "_status",
        "_status_message",
        "_trace_id",
    )

    def __init__(
        self,
        *,
        name: str,
        kind: SpanKind,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        start_time: datetime,
    ) -> None:
        self._name = name
        self._kind = kind
        self._trace_id = trace_id
        self._span_id = span_id
        self._parent_span_id = parent_span_id
        self._start_time = start_time
        self._end_time: datetime | None = None
        self._status: SpanStatus = "ok"
        self._status_message: str | None = None
        self._attributes: dict[str, str] = {}
        self._events: list[SpanEvent] = []

    # --- mutation API -------------------------------------------------

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        """Pin an attribute on the span. Accepts scalars, stringifies them."""
        self._attributes[key] = str(value)

    def set_status(self, status: SpanStatus, message: str | None = None) -> None:
        self._status = status
        self._status_message = message

    def add_event(self, name: str, attributes: dict[str, str] | None = None) -> None:
        self._events.append(
            SpanEvent(
                name=name,
                timestamp=datetime.now(UTC),
                attributes=attributes or {},
            )
        )

    # --- accessors used by tests + exporters --------------------------

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def span_id(self) -> str:
        return self._span_id

    @property
    def parent_span_id(self) -> str | None:
        return self._parent_span_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def kind(self) -> SpanKind:
        return self._kind

    def attributes_snapshot(self) -> dict[str, str]:
        return dict(self._attributes)

    def to_span(self) -> Span:
        """Materialize the immutable Span for export."""
        return Span(
            trace_id=self._trace_id,
            span_id=self._span_id,
            parent_span_id=self._parent_span_id,
            name=self._name,
            kind=self._kind,
            start_time=self._start_time,
            end_time=self._end_time,
            status=self._status,
            status_message=self._status_message,
            attributes=dict(self._attributes),
            events=list(self._events),
        )


# ---------------------------------------------------------------------------
# Public hooks for cross-product integration (e.g. tokencost)
# ---------------------------------------------------------------------------


def current_span() -> SpanHandle | None:
    """Return the currently-active span, or None.

    External libraries (tokencost, custom telemetry middlewares) call
    this to find the right span to attach attributes to. Always
    safe to call -- returns None when no agtrace block is active.
    """
    return _current.get()


def attach_attributes(attributes: dict[str, str | int | float | bool]) -> bool:
    """Pin attributes on the active span. Returns True iff a span was active.

    Designed to be called by integration code that runs OUTSIDE a
    `with tracer.span(...)` block but still wants to enrich it --
    e.g. tokencost's SDK middleware records token counts and cost
    on the surrounding `prompt`-kind span without the user having
    to pass the span through.

    No-op (returns False) when nothing is active. Never raises.
    """
    cur = _current.get()
    if cur is None:
        return False
    for key, value in attributes.items():
        try:
            cur.set_attribute(key, value)
        except Exception:
            # Per-attribute failure must not abort the rest. Worst case
            # the trace is missing one row of data.
            continue
    return True


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


class Tracer:
    """The thing apps interact with."""

    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    @contextmanager
    def span(
        self,
        name: str,
        *,
        kind: SpanKind = "unknown",
        attributes: dict[str, str] | None = None,
    ) -> Iterator[SpanHandle]:
        """Start a span. Use as a context manager to auto-close.

        On exception inside the block: status is set to 'error' and the
        exception type + message are recorded as attributes. The
        exception still propagates -- the tracer never swallows errors.
        """
        parent = _current.get()
        trace_id = parent.trace_id if parent is not None else _new_trace_id()
        parent_span_id = parent.span_id if parent is not None else None

        handle = SpanHandle(
            name=name,
            kind=kind,
            trace_id=trace_id,
            span_id=_new_span_id(),
            parent_span_id=parent_span_id,
            start_time=datetime.now(UTC),
        )
        if attributes:
            for k, v in attributes.items():
                handle.set_attribute(k, v)

        token = _current.set(handle)
        try:
            yield handle
        except Exception as exc:
            handle.set_status("error", f"{type(exc).__name__}: {exc}")
            handle.set_attribute("exception.type", type(exc).__name__)
            raise
        finally:
            handle._end_time = datetime.now(UTC)
            _current.reset(token)
            try:
                self._exporter(handle.to_span())
            except Exception as exc:
                # Exporter failures must never break the user's code.
                logger.warning("agtrace exporter failed: %s", exc)


# ---------------------------------------------------------------------------
# Default exporter (JSONL append)
# ---------------------------------------------------------------------------


def jsonl_exporter(path: Path) -> SpanExporter:
    """Return an exporter that appends each span as one JSON line."""

    def _export(span: Span) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(span.model_dump_json(exclude_none=False))
            f.write("\n")

    return _export


def default_tracer(path: Path | None = None) -> Tracer:
    """Convenience: a tracer that writes to `.agtrace/traces.jsonl`."""
    target = path or Path(".agtrace/traces.jsonl")
    return Tracer(exporter=jsonl_exporter(target))


def in_memory_tracer() -> tuple[Tracer, list[Span]]:
    """Tracer that stores spans in a list. Used by tests."""
    captured: list[Span] = []

    def _export(span: Span) -> None:
        captured.append(span)

    return Tracer(exporter=_export), captured
