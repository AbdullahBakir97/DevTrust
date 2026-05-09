"""Smoke tests for AgentGuard v0.0.1.

Coverage:
  - Pydantic models (Policy, Rule, ToolCall, Decision) accept/reject as expected.
  - evaluate(): first-rule-wins, default-deny, when-dict subset matching,
    fnmatch tool patterns.
  - enforce(): writes to JSONL audit log, decision matches evaluate output.
  - identity: with_agent / current_agent ContextVar stack.
  - baseline policies fire on representative inputs.
  - CLI: version, policies, check (allow / deny / unknown policy / bad JSON).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest
from agentguard import (
    SCHEMA_VERSION,
    Decision,
    Policy,
    Rule,
    ToolCall,
    __version__,
    current_agent,
    enforce,
    evaluate,
    with_agent,
)
from agentguard.baseline import (
    baseline_starter_policy,
    deny_destructive_filesystem,
    deny_money_movement,
)
from agentguard.cli import app
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_schema_version_pinned() -> None:
    """The on-disk schema is a stability contract; pin v0.0.1 here."""
    assert SCHEMA_VERSION == "0.0.1"


def test_agentguard_version_is_semver_shaped() -> None:
    """Structural check, survives bumps without edits."""
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-+].+)?", __version__), __version__


def test_rule_requires_nonempty_reason() -> None:
    with pytest.raises(ValueError):
        Rule(name="r", effect="deny", reason="")


def test_policy_default_rules_is_empty_list() -> None:
    p = Policy(name="empty")
    assert p.rules == []
    assert p.schema_version == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Engine — evaluate
# ---------------------------------------------------------------------------


def test_evaluate_default_deny_when_no_rule_matches() -> None:
    policy = Policy(name="empty")
    call = ToolCall(tool="fs.read", arguments={})
    decision = evaluate(policy, call)
    assert decision.status == "deny"
    assert decision.matched_rule is None
    assert "No rule" in decision.reason


def test_evaluate_first_matching_rule_wins(simple_allow_policy: Policy) -> None:
    call = ToolCall(tool="fs.read", arguments={"path": "/tmp/x"})
    decision = evaluate(simple_allow_policy, call)
    assert decision.status == "allow"
    assert decision.matched_rule == "allow-fs-read"


def test_evaluate_unmatched_call_gets_default_deny(simple_allow_policy: Policy) -> None:
    call = ToolCall(tool="fs.write", arguments={"path": "/tmp/x"})
    decision = evaluate(simple_allow_policy, call)
    assert decision.status == "deny"
    assert decision.matched_rule is None


def test_evaluate_when_dict_subset_matching() -> None:
    """A rule's `when` clause requires ALL key/value pairs to match."""
    policy = Policy(
        name="cond",
        rules=[
            Rule(
                name="deny-recursive-only",
                effect="deny",
                tool="fs.delete",
                when={"recursive": True},
                reason="No recursive deletes.",
            ),
            Rule(
                name="allow-non-recursive",
                effect="allow",
                tool="fs.delete",
                reason="Single-file deletes are fine.",
            ),
        ],
    )
    recursive_call = ToolCall(tool="fs.delete", arguments={"recursive": True, "path": "/tmp/x"})
    single_call = ToolCall(tool="fs.delete", arguments={"recursive": False, "path": "/tmp/x"})

    assert evaluate(policy, recursive_call).status == "deny"
    assert evaluate(policy, single_call).status == "allow"


def test_evaluate_fnmatch_tool_glob() -> None:
    policy = Policy(
        name="globs",
        rules=[
            Rule(name="deny-stripe", effect="deny", tool="stripe.*", reason="No stripe."),
        ],
    )
    assert evaluate(policy, ToolCall(tool="stripe.charge")).status == "deny"
    assert evaluate(policy, ToolCall(tool="stripe.refund")).status == "deny"
    # Different namespace -> default deny still fires (no rule matched).
    assert evaluate(policy, ToolCall(tool="paypal.charge")).status == "deny"


def test_evaluate_uses_current_agent_when_call_agent_is_none() -> None:
    policy = Policy(name="p")
    call = ToolCall(tool="fs.read")
    with with_agent("pr-reviewer-bot"):
        decision = evaluate(policy, call)
    assert decision.agent == "pr-reviewer-bot"


def test_evaluate_explicit_call_agent_overrides_current() -> None:
    policy = Policy(name="p")
    call = ToolCall(tool="fs.read", agent="explicit-agent")
    with with_agent("context-agent"):
        decision = evaluate(policy, call)
    assert decision.agent == "explicit-agent"


# ---------------------------------------------------------------------------
# Engine — enforce + audit log
# ---------------------------------------------------------------------------


def test_enforce_writes_decision_to_audit_jsonl(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    policy = Policy(
        name="p",
        rules=[Rule(name="allow-read", effect="allow", tool="fs.read", reason="ok")],
    )
    decision = enforce(policy, ToolCall(tool="fs.read"), audit=audit)
    assert decision.status == "allow"
    assert audit.is_file()
    rows = audit.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    parsed = Decision.model_validate_json(rows[0])
    assert parsed.status == "allow"
    assert parsed.matched_rule == "allow-read"
    assert isinstance(parsed.timestamp, datetime)


def test_enforce_appends_across_calls(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    policy = Policy(name="p")  # default-deny
    enforce(policy, ToolCall(tool="fs.read"), audit=audit)
    enforce(policy, ToolCall(tool="fs.write"), audit=audit)
    rows = audit.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 2


def test_enforce_creates_parent_dir(tmp_path: Path) -> None:
    audit = tmp_path / "deep" / "nested" / "audit.jsonl"
    enforce(Policy(name="p"), ToolCall(tool="x"), audit=audit)
    assert audit.is_file()


def test_enforce_without_audit_path_skips_writing(tmp_path: Path) -> None:
    """Audit is optional. Decision is still returned; nothing is written."""
    decision = enforce(Policy(name="p"), ToolCall(tool="x"))
    assert decision.status == "deny"
    # No file should appear in tmp_path
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Identity (ContextVar stack)
# ---------------------------------------------------------------------------


def test_current_agent_returns_none_outside_block() -> None:
    assert current_agent() is None


def test_with_agent_sets_and_restores() -> None:
    assert current_agent() is None
    with with_agent("outer"):
        assert current_agent() == "outer"
    assert current_agent() is None


def test_with_agent_nests_correctly() -> None:
    with with_agent("outer"):
        assert current_agent() == "outer"
        with with_agent("inner"):
            assert current_agent() == "inner"
        assert current_agent() == "outer"
    assert current_agent() is None


# ---------------------------------------------------------------------------
# Baseline policies
# ---------------------------------------------------------------------------


def test_baseline_money_movement_denies_stripe_charge() -> None:
    decision = evaluate(deny_money_movement(), ToolCall(tool="stripe.charge"))
    assert decision.status == "deny"
    assert "owasp:llm05" in decision.tags


def test_baseline_money_movement_denies_bank_transfer() -> None:
    decision = evaluate(deny_money_movement(), ToolCall(tool="bank.transfer"))
    assert decision.status == "deny"


def test_baseline_destructive_filesystem_denies_recursive_delete() -> None:
    call = ToolCall(tool="fs.delete", arguments={"recursive": True})
    decision = evaluate(deny_destructive_filesystem(), call)
    assert decision.status == "deny"
    assert decision.matched_rule == "deny-fs-delete-recursive"


def test_baseline_destructive_filesystem_allows_when_recursive_is_false() -> None:
    """Without recursive=True, the recursive-delete rule doesn't match.

    The rmtree rule is unconditional and would fire only on `fs.rmtree`.
    A non-recursive `fs.delete` falls through to default-deny — which is
    still a deny but for a different reason. Confirm the matched_rule is
    None (default deny), not the recursive-delete rule.
    """
    call = ToolCall(tool="fs.delete", arguments={"recursive": False})
    decision = evaluate(deny_destructive_filesystem(), call)
    assert decision.status == "deny"
    assert decision.matched_rule is None  # fell through to default-deny


def test_baseline_starter_composes_all_three() -> None:
    starter = baseline_starter_policy()
    # Should contain rules from all three baseline groups.
    rule_names = {r.name for r in starter.rules}
    assert "deny-stripe-charge" in rule_names
    assert "deny-fs-rmtree" in rule_names
    assert "deny-mail-send-with-secret" in rule_names


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_version_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    # Strip ANSI escape codes for substring check (CI sets FORCE_COLOR=1).
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert __version__ in plain


def test_cli_policies_lists_baselines() -> None:
    result = runner.invoke(app, ["policies"])
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "baseline-starter" in plain
    assert "money-movement" in plain
    assert "destructive-filesystem" in plain
    assert "credential-disclosure" in plain


def test_cli_check_denies_stripe_charge() -> None:
    result = runner.invoke(
        app,
        ["check", "--tool", "stripe.charge", "--policy", "baseline-starter"],
    )
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "DENY" in plain


def test_cli_check_unknown_policy_errors() -> None:
    result = runner.invoke(
        app,
        ["check", "--tool", "fs.read", "--policy", "nope"],
    )
    assert result.exit_code == 2


def test_cli_check_rejects_invalid_arguments_json() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            "--tool",
            "fs.delete",
            "--policy",
            "destructive-filesystem",
            "--arguments-json",
            "{not valid json",
        ],
    )
    assert result.exit_code != 0


def test_cli_check_arguments_json_routes_to_recursive_rule() -> None:
    """--arguments-json '{"recursive":true}' should hit the recursive rule."""
    result = runner.invoke(
        app,
        [
            "check",
            "--tool",
            "fs.delete",
            "--policy",
            "destructive-filesystem",
            "--arguments-json",
            json.dumps({"recursive": True}),
        ],
    )
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "DENY" in plain
    assert "deny-fs-delete-recursive" in plain
