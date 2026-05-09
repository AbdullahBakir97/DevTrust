"""ContextVar-based agent identity.

When an agent runtime calls `evaluate(policy, call)`, the `call.agent` field
should identify which agent attempted the action. Passing the agent ID
through every layer of code is awkward; instead, AgentGuard uses a
ContextVar that the agent runtime sets once per agent invocation:

    with with_agent("pr-reviewer:installation-12345"):
        agent.run(...)

Inside that block, any ToolCall constructed without an explicit `agent=`
field inherits the current value. ContextVar is correct under both
threading and asyncio — the same pattern used in agtrace and tokencost.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_current_agent: ContextVar[str | None] = ContextVar("agentguard.current_agent", default=None)


def current_agent() -> str | None:
    """Return the currently-bound agent identifier, or None if not set."""
    return _current_agent.get()


@contextmanager
def with_agent(agent: str) -> Iterator[None]:
    """Bind `agent` for the duration of the with-block.

    Nested calls stack correctly: leaving an inner block restores the
    outer agent identifier (via ContextVar.reset).
    """
    token = _current_agent.set(agent)
    try:
        yield
    finally:
        _current_agent.reset(token)
