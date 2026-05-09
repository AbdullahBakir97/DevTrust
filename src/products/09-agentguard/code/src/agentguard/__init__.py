"""AgentGuard — policy-as-code runtime for AI agents.

The Wave 4 governance layer of the DevTrust platform. AgentGuard sits between
an AI agent and its tools and decides, on every tool call, whether the call
is permitted by the active policy. Decisions are logged to an append-only
audit trail (JSONL) so every action — allowed, denied, or escalated — is
traceable end-to-end.

v0.0.1 scope (deterministic-only, library-mode):

  - `Policy`, `Rule`, `ToolCall`, `Decision` Pydantic models.
  - `evaluate(policy, call)` — pure function, no side effects, returns a
    Decision with the matched rule(s) and the reason.
  - `enforce(policy, call, *, audit=...)` — convenience wrapper that calls
    evaluate AND records the Decision to the audit JSONL.
  - ContextVar-based agent identity so the SAME tool function can be wrapped
    once and behave correctly across threads / async tasks.
  - CLI: `agentguard version`, `agentguard check`, `agentguard policies`.

Out of scope for v0.0.1 (intentional, will land in v0.1+):

  - Policy DSL parser (YAML / TOML / DSL surface — v0.1 ships YAML).
  - Approval workflows (Slack / email round-trip — v0.2).
  - OWASP Top-10 detector pack (v0.1 ships baseline rules).
  - Replay + time-travel debugging via agtrace (v0.3).
"""

from __future__ import annotations

__version__ = "0.0.1"

from agentguard.engine import enforce, evaluate
from agentguard.identity import current_agent, with_agent
from agentguard.models import (
    SCHEMA_VERSION,
    Decision,
    DecisionStatus,
    Policy,
    Rule,
    RuleEffect,
    ToolCall,
)

__all__ = [
    "SCHEMA_VERSION",
    "Decision",
    "DecisionStatus",
    "Policy",
    "Rule",
    "RuleEffect",
    "ToolCall",
    "__version__",
    "current_agent",
    "enforce",
    "evaluate",
    "with_agent",
]
