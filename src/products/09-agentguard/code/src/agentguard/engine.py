"""Policy evaluation engine.

`evaluate(policy, call)` is the pure function that decides whether a tool
call is permitted by a policy. `enforce(policy, call, audit=...)` is a
convenience wrapper that calls evaluate AND appends the Decision to an
audit log file.

The evaluation algorithm (v0.0.1):

  1. Resolve the agent: if call.agent is None, read from current_agent().
  2. Walk policy.rules in order.
  3. For each rule:
     a. Check tool-name match via fnmatch (rule.tool is a glob).
     b. Check that every key in rule.when matches call.arguments. A missing
        key in arguments is treated as "no match".
  4. The FIRST rule that matches decides the outcome.
  5. If no rule matches, the default is 'deny' (conservative-by-default).
"""

from __future__ import annotations

import fnmatch
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from agentguard.identity import current_agent
from agentguard.models import Decision, Policy, ToolCall

if TYPE_CHECKING:
    from agentguard.models import Rule


def _rule_matches(rule: Rule, call: ToolCall) -> bool:
    """True if `rule` applies to `call` (tool-name glob + when-dict subset)."""
    if not fnmatch.fnmatchcase(call.tool, rule.tool):
        return False
    return all(call.arguments.get(key) == expected for key, expected in rule.when.items())


def evaluate(policy: Policy, call: ToolCall) -> Decision:
    """Run `policy` against `call` and return a Decision.

    Pure function: no I/O, no side effects, deterministic. Use this for
    unit tests, dry-runs, and policy preview / "shadow mode" deployments
    where you want to log decisions without actually enforcing them.
    """
    agent = call.agent if call.agent is not None else current_agent()
    now = datetime.now(UTC)

    for rule in policy.rules:
        if _rule_matches(rule, call):
            return Decision(
                timestamp=now,
                status=rule.effect,
                tool=call.tool,
                agent=agent,
                arguments=dict(call.arguments),
                matched_rule=rule.name,
                reason=rule.reason,
                tags=list(rule.tags),
            )

    # Conservative default: nothing matched -> deny.
    return Decision(
        timestamp=now,
        status="deny",
        tool=call.tool,
        agent=agent,
        arguments=dict(call.arguments),
        matched_rule=None,
        reason=(
            "No rule in this policy matched the tool call. "
            "Default policy is deny (conservative-by-default). "
            "Add an explicit Rule(effect='allow', ...) to permit it."
        ),
        tags=[],
    )


def enforce(
    policy: Policy,
    call: ToolCall,
    *,
    audit: Path | None = None,
) -> Decision:
    """Evaluate `call` against `policy` AND record the decision to `audit`.

    `audit` is the path to a JSONL file. One JSON object per line, ordered
    by call. The file is created if missing; appended to if present.

    Returns the Decision so the caller can branch on `decision.status`:
      - 'allow' -> proceed with the underlying tool.
      - 'deny'  -> raise / surface a refusal message back to the agent.
      - 'require_approval' -> v0.0.1 doesn't ship the round-trip, treat as deny
        for now and log the request. v0.2 wires this to Slack/Teams/email.
    """
    decision = evaluate(policy, call)
    if audit is not None:
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("a", encoding="utf-8") as fh:
            fh.write(decision.model_dump_json() + "\n")
    return decision
