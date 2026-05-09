"""Per-call attribution context for TokenCost middlewares.

Operators set wrap-time defaults (`wrap(client, feature='pr-review')`)
but for many use cases the attribution depends on what the calling
code is doing right now: the same client serves multiple features.

The `attribution()` context manager fills that gap. It uses a
`ContextVar` so it composes cleanly under asyncio + threads + nested
spans -- the active attribution is whatever is most-recently entered.

    with attribution(feature="pr-review", actor="acme"):
        client.messages.create(...)   # recorded with these attrs

    with attribution(feature="search"):
        with attribution(actor="globex"):
            client.messages.create(...)   # feature=search, actor=globex
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

# `None` is the sentinel for 'nothing in scope'. We materialize an
# empty dict on first read via _read_active().
_active: ContextVar[dict[str, str] | None] = ContextVar("tokencost_attribution", default=None)


def _read_active() -> dict[str, str]:
    raw = _active.get()
    return dict(raw) if raw is not None else {}


@contextmanager
def attribution(
    *,
    feature: str | None = None,
    environment: str | None = None,
    actor: str | None = None,
    request_id: str | None = None,
) -> Iterator[None]:
    """Set attribution fields for any TokenCost-tracked call inside the block.

    Fields with value None are NOT applied -- they let the caller scope
    only the dimension they care about without overriding parent context.
    """
    incoming: dict[str, str] = {}
    if feature is not None:
        incoming["feature"] = feature
    if environment is not None:
        incoming["environment"] = environment
    if actor is not None:
        incoming["actor"] = actor
    if request_id is not None:
        incoming["request_id"] = request_id

    parent = _read_active()
    merged = {**parent, **incoming}
    token = _active.set(merged)
    try:
        yield
    finally:
        _active.reset(token)


def current() -> dict[str, str]:
    """Read-only snapshot of the active attribution. Mostly used by tests."""
    return _read_active()


def merged_with(defaults: dict[str, str | None]) -> dict[str, str | None]:
    """Combine wrap-time defaults with the active context.

    Active context wins on conflicts -- the operator scoped this block
    on purpose. Returns a new dict; never mutates inputs.
    """
    out: dict[str, str | None] = {}
    out.update({k: v for k, v in defaults.items() if v is not None})
    out.update(_read_active())
    return out
