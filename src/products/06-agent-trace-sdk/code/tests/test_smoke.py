"""Smoke + unit tests for agtrace v0.0.1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agtrace import __version__
from agtrace.cli import app
from agtrace.models import SCHEMA_VERSION, Span
from agtrace.tracer import (
    Tracer,
    default_tracer,
    in_memory_tracer,
    jsonl_exporter,
)
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# id generation + version
# ---------------------------------------------------------------------------


def test_schema_and_tool_versions() -> None:
    """Schema is pinned at 0.0.1; tool version moves forward independently.

    The point of this test isn't to assert the current version number
    (which we'd have to update on every bump) -- it's to confirm the
    schema stays stable while the tool version is a valid SemVer.
    """
    import re as _re

    assert SCHEMA_VERSION == "0.0.1"
    assert _re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", __version__) is not None


def test_root_span_has_no_parent_and_unique_trace(
    captured_tracer: tuple[Tracer, list[Span]],
) -> None:
    tracer, captured = captured_tracer
    with tracer.span("root", kind="agent") as s:
        assert s.parent_span_id is None
        assert len(s.trace_id) == 32
        assert len(s.span_id) == 16
    assert len(captured) == 1
    span = captured[0]
    assert span.parent_span_id is None
    assert span.status == "ok"


def test_nested_spans_share_trace_and_chain_parents(
    captured_tracer: tuple[Tracer, list[Span]],
) -> None:
    tracer, captured = captured_tracer
    with tracer.span("agent.run", kind="agent") as outer:
        outer_trace = outer.trace_id
        outer_id = outer.span_id
        with tracer.span("llm.call", kind="prompt") as inner:
            assert inner.trace_id == outer_trace
            assert inner.parent_span_id == outer_id
    # Both spans exported
    assert len(captured) == 2
    # Inner span closed first; outer second.
    assert captured[0].name == "llm.call"
    assert captured[1].name == "agent.run"
    # Both share trace_id
    assert captured[0].trace_id == captured[1].trace_id


def test_set_attribute_and_event(
    captured_tracer: tuple[Tracer, list[Span]],
) -> None:
    tracer, captured = captured_tracer
    with tracer.span("llm.call", kind="prompt") as s:
        s.set_attribute("model", "claude-sonnet-4-6")
        s.set_attribute("max_tokens", 1024)
        s.add_event("rate-limited", attributes={"retry_after": "1.5"})
    assert captured[0].attributes["model"] == "claude-sonnet-4-6"
    assert captured[0].attributes["max_tokens"] == "1024"  # stringified
    assert len(captured[0].events) == 1
    assert captured[0].events[0].name == "rate-limited"


def test_exception_marks_status_error_and_propagates(
    captured_tracer: tuple[Tracer, list[Span]],
) -> None:
    tracer, captured = captured_tracer
    with pytest.raises(ValueError, match="boom"), tracer.span("agent.run", kind="agent"):
        raise ValueError("boom")
    assert captured[0].status == "error"
    assert "ValueError" in (captured[0].status_message or "")
    assert captured[0].attributes["exception.type"] == "ValueError"


def test_exporter_failure_does_not_break_caller(tmp_path: Path) -> None:
    """A misbehaving exporter must NOT crash the user's code."""

    def boom_exporter(_span: Span) -> None:
        raise RuntimeError("export went sideways")

    tracer = Tracer(exporter=boom_exporter)
    # Should not raise
    with tracer.span("noop"):
        pass


# ---------------------------------------------------------------------------
# JSONL exporter / default tracer
# ---------------------------------------------------------------------------


def test_jsonl_exporter_round_trip(jsonl_path: Path) -> None:
    tracer = Tracer(exporter=jsonl_exporter(jsonl_path))
    with tracer.span("agent.run", kind="agent") as outer:
        outer.set_attribute("agent", "pr-reviewer")
        with tracer.span("llm.call", kind="prompt") as inner:
            inner.set_attribute("model", "claude-sonnet-4-6")

    text = jsonl_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    names = {r["name"] for r in rows}
    assert names == {"agent.run", "llm.call"}
    # Validate parses back through the schema and shares one trace_id.
    parsed = [Span.model_validate(r) for r in rows]
    assert all(p.trace_id == parsed[0].trace_id for p in parsed)
    # Both spans recorded their attributes through the round-trip.
    by_name = {p.name: p for p in parsed}
    assert by_name["agent.run"].attributes["agent"] == "pr-reviewer"
    assert by_name["llm.call"].attributes["model"] == "claude-sonnet-4-6"


def test_default_tracer_writes_to_default_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Confirm `default_tracer()` defaults to `.agtrace/traces.jsonl`
    relative to the current dir."""
    monkeypatch.chdir(tmp_path)
    tracer = default_tracer()
    with tracer.span("hello"):
        pass
    assert (tmp_path / ".agtrace" / "traces.jsonl").is_file()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_version_prints_version() -> None:
    import re

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    # Rich emits ANSI escape codes when CI sets FORCE_COLOR=1; strip them
    # so the substring check works regardless of terminal styling.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert __version__ in plain


def test_cli_dump_renders_tree(tmp_path: Path) -> None:
    """The dump command pretty-prints a trace tree and exits 0."""
    jsonl = tmp_path / "traces.jsonl"
    tracer = Tracer(exporter=jsonl_exporter(jsonl))
    with tracer.span("agent.run", kind="agent") as outer:
        outer.set_attribute("agent", "pr-reviewer")
        with tracer.span("llm.call", kind="prompt") as inner:
            inner.set_attribute("model", "claude-sonnet-4-6")

    result = runner.invoke(app, ["dump", "--from-file", str(jsonl)])
    assert result.exit_code == 0, result.stdout
    # The two span names must appear in the rendered tree
    assert "agent.run" in result.stdout
    assert "llm.call" in result.stdout


def test_cli_dump_handles_empty_input(tmp_path: Path) -> None:
    empty = tmp_path / "nothing.jsonl"
    empty.write_text("", encoding="utf-8")
    result = runner.invoke(app, ["dump", "--from-file", str(empty)])
    assert result.exit_code == 0
    assert "No spans" in result.stdout


def test_in_memory_tracer_captures_in_order(
    captured_tracer: tuple[Tracer, list[Span]],
) -> None:
    """First-closed-first ordering -- inner spans land before their parents."""
    tracer, captured = captured_tracer
    with tracer.span("a"), tracer.span("b"), tracer.span("c"):
        pass
    assert [s.name for s in captured] == ["c", "b", "a"]


def test_in_memory_tracer_independent_traces() -> None:
    """Two top-level spans get two distinct trace_ids."""
    tracer, captured = in_memory_tracer()
    with tracer.span("root1"):
        pass
    with tracer.span("root2"):
        pass
    assert len({s.trace_id for s in captured}) == 2


def test_span_kind_attribute_persists(
    captured_tracer: tuple[Tracer, list[Span]],
) -> None:
    tracer, captured = captured_tracer
    with tracer.span("retry-attempt", kind="retry"):
        pass
    assert captured[0].kind == "retry"


# ---------------------------------------------------------------------------
# v0.0.2: public hooks (current_span / attach_attributes) for cross-product
# ---------------------------------------------------------------------------


def test_current_span_returns_none_outside_block() -> None:
    from agtrace.tracer import current_span

    assert current_span() is None


def test_current_span_returns_handle_inside_block(
    captured_tracer: tuple[Tracer, list[Span]],
) -> None:
    tracer, _ = captured_tracer
    from agtrace.tracer import current_span

    with tracer.span("agent.run", kind="agent") as s:
        cur = current_span()
        assert cur is not None
        assert cur.span_id == s.span_id
    # Block exited -> back to None
    assert current_span() is None


def test_attach_attributes_to_active_span(
    captured_tracer: tuple[Tracer, list[Span]],
) -> None:
    tracer, captured = captured_tracer
    from agtrace.tracer import attach_attributes

    with tracer.span("llm.call", kind="prompt"):
        attached = attach_attributes(
            {
                "tokens.input": 1234,
                "tokens.output": 567,
                "cost.usd": "$0.0042",
            }
        )
        assert attached is True
    span = captured[0]
    # Integers are stringified by SpanHandle.set_attribute
    assert span.attributes["tokens.input"] == "1234"
    assert span.attributes["tokens.output"] == "567"
    assert span.attributes["cost.usd"] == "$0.0042"


def test_attach_attributes_outside_block_is_noop() -> None:
    from agtrace.tracer import attach_attributes

    attached = attach_attributes({"x": 1})
    assert attached is False  # nothing to attach to; nobody crashed
