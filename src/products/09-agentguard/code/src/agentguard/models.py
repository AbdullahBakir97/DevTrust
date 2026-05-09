"""Pydantic models for AgentGuard.

The shape of these models is the public API of the package. Downstream
consumers (the audit-log reader, dashboards, the v0.1 YAML policy parser)
read these types. Treat changes as breaking and bump SCHEMA_VERSION.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.0.1"


# ---------------------------------------------------------------------------
# Tool calls
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    """One attempted tool invocation by an agent.

    The agent's runtime constructs this and hands it to AgentGuard before
    actually invoking the tool. AgentGuard returns a Decision; the runtime
    only proceeds with the underlying tool if Decision.status == 'allow'.
    """

    model_config = ConfigDict(frozen=True)

    tool: str = Field(
        ...,
        description=(
            "Stable identifier for the tool. Convention: 'namespace.action' "
            "(e.g. 'stripe.charge', 'fs.write', 'mail.send')."
        ),
    )
    arguments: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Tool-specific arguments. AgentGuard does NOT execute these — "
            "it only inspects them for policy match. Sensitive values "
            "should be redacted before construction."
        ),
    )
    agent: str | None = Field(
        default=None,
        description=(
            "Agent identifier (free-form, but stable across runs). When "
            "None, AgentGuard reads from the current_agent() ContextVar."
        ),
    )


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


RuleEffect = Literal["allow", "deny", "require_approval"]


class Rule(BaseModel):
    """One rule in a policy.

    v0.0.1 supports tool-name globbing via fnmatch (e.g. `tool='stripe.*'`)
    plus an optional `when` predicate over arguments, expressed as a
    {key: expected_value} dict. v0.1 will replace `when` with a real
    expression DSL; v0.0.1's dict form is intentionally simple.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1)
    effect: RuleEffect
    tool: str = Field(
        default="*",
        description="Tool-name fnmatch pattern. Default '*' matches every tool.",
    )
    when: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Argument predicate as a flat dict; ALL key/value pairs must "
            "match the call's arguments for the rule to apply. v0.1 lifts "
            "this to a real expression DSL."
        ),
    )
    reason: str = Field(
        ...,
        min_length=1,
        description=(
            "Compliance-team-readable explanation. Surfaced in the audit "
            "log and in any approval/denial message back to the agent."
        ),
    )
    tags: list[str] = Field(
        default_factory=list,
        description=(
            "Free-form tags ('owasp:llm05', 'pii', 'soc2:cc6.1'). Used by "
            "compliance reports and dashboards."
        ),
    )


class Policy(BaseModel):
    """A policy is an ordered list of rules.

    Evaluation walks the rules in order. The FIRST rule that matches
    decides the outcome. If no rule matches, the default is 'deny' --
    conservative-by-default. (v0.1 ships an explicit `default_effect`
    field on Policy; v0.0.1 keeps the deny default hard-coded.)
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    name: str = Field(..., min_length=1)
    description: str = ""
    rules: list[Rule] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


DecisionStatus = Literal["allow", "deny", "require_approval"]


class Decision(BaseModel):
    """The result of policy-evaluating one ToolCall.

    Persisted to the audit JSONL exactly as-is — no transformation between
    in-memory and on-disk shape, by design. Downstream readers (compliance
    dashboards, future replay tooling) deserialize directly into Decision.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    timestamp: datetime
    status: DecisionStatus
    tool: str
    agent: str | None = None
    arguments: dict[str, object] = Field(default_factory=dict)

    matched_rule: str | None = Field(
        default=None,
        description=(
            "Name of the matching Rule, or None if no rule matched and the default deny fired."
        ),
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Compliance-team-readable explanation of this decision.",
    )
    tags: list[str] = Field(default_factory=list)
