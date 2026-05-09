"""Smoke + unit tests for tokencost v0.0.1."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tokencost import __version__
from tokencost.aggregate import aggregate
from tokencost.cli import app
from tokencost.models import (
    MICROS_PER_USD,
    SCHEMA_VERSION,
    TokenUsage,
)
from tokencost.prices import (
    ModelPrice,
    add_model,
    estimate_cost_micros,
    get_price,
    known_models,
)
from tokencost.store import append, load
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# prices
# ---------------------------------------------------------------------------


def test_known_models_includes_baseline_set() -> None:
    names = {(p.provider, p.model) for p in known_models()}
    assert ("anthropic", "claude-sonnet-4-6") in names
    assert ("anthropic", "claude-haiku-4-5") in names
    assert ("openai", "gpt-5") in names


def test_get_price_returns_none_for_unknown() -> None:
    assert get_price("anthropic", "claude-zzz-99") is None


def test_model_price_cost_calc_uses_integer_arithmetic() -> None:
    """1M input + 1M output at $3 / $15 should be $18 -- exactly."""
    p = ModelPrice(
        provider="x",
        model="y",
        input_micros_per_mtok=3 * MICROS_PER_USD,
        output_micros_per_mtok=15 * MICROS_PER_USD,
    )
    cost = p.cost_micros(1_000_000, 1_000_000)
    assert cost == 18 * MICROS_PER_USD


def test_estimate_cost_micros_for_known_model() -> None:
    cost = estimate_cost_micros("anthropic", "claude-haiku-4-5", 1_000_000, 1_000_000)
    # Haiku is $1 in + $5 out per 1M -> $6 total
    assert cost == 6 * MICROS_PER_USD


def test_add_model_overrides_at_runtime() -> None:
    custom = ModelPrice(
        provider="local",
        model="my-tuned",
        input_micros_per_mtok=0,
        output_micros_per_mtok=0,
    )
    add_model(custom)
    assert get_price("local", "my-tuned") == custom


# ---------------------------------------------------------------------------
# store
# ---------------------------------------------------------------------------


def test_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    u = TokenUsage(
        timestamp=datetime(2026, 5, 8, 12, tzinfo=UTC),
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cost_micros=42,
        feature="pr-review",
    )
    append(path, u)
    rows = list(load(path))
    assert len(rows) == 1
    assert rows[0].cost_micros == 42
    assert rows[0].feature == "pr-review"


def test_store_skips_malformed_lines(tmp_path: Path) -> None:
    """A bad line in the middle should not abort the load."""
    path = tmp_path / "usage.jsonl"
    good = TokenUsage(
        timestamp=datetime(2026, 5, 8, 12, tzinfo=UTC),
        provider="x",
        model="y",
        input_tokens=1,
        output_tokens=1,
        cost_micros=1,
    )
    path.write_text(
        good.model_dump_json() + "\n" + "not even close to JSON\n" + good.model_dump_json() + "\n",
        encoding="utf-8",
    )
    rows = list(load(path))
    assert len(rows) == 2


def test_store_load_missing_file_returns_empty(tmp_path: Path) -> None:
    rows = list(load(tmp_path / "nope.jsonl"))
    assert rows == []


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


def test_aggregate_empty_input_produces_zero_report() -> None:
    rep = aggregate([])
    assert rep.total_calls == 0
    assert rep.total_cost_micros == 0
    assert rep.by_feature == []


def test_aggregate_totals(sample_usage: list[TokenUsage]) -> None:
    rep = aggregate(sample_usage)
    assert rep.total_calls == 4
    assert rep.total_input_tokens == sum(u.input_tokens for u in sample_usage)
    assert rep.total_cost_micros == sum(u.cost_micros for u in sample_usage)


def test_aggregate_by_feature_sorted_descending(sample_usage: list[TokenUsage]) -> None:
    """The most expensive feature should land first; '(unset)' bucket exists."""
    rep = aggregate(sample_usage)
    labels_in_order = [b.label for b in rep.by_feature]
    # pr-review has the heaviest spend (sonnet $6 + gpt-5 $3.50 = $9.50).
    assert labels_in_order[0] == "pr-review"
    assert "(unset)" in labels_in_order
    # Sorted descending by cost
    costs = [b.cost_micros for b in rep.by_feature]
    assert costs == sorted(costs, reverse=True)


def test_aggregate_by_model_breakdown(sample_usage: list[TokenUsage]) -> None:
    rep = aggregate(sample_usage)
    by_model = {b.label: b for b in rep.by_model}
    assert "claude-sonnet-4-6" in by_model
    assert "claude-haiku-4-5" in by_model
    assert "gpt-5" in by_model


def test_aggregate_window_covers_earliest_to_latest(
    sample_usage: list[TokenUsage],
) -> None:
    rep = aggregate(sample_usage)
    timestamps = [u.timestamp for u in sample_usage]
    assert rep.window_start == min(timestamps)
    assert rep.window_end == max(timestamps)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_version_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_prices_lists_known_models() -> None:
    result = runner.invoke(app, ["prices"])
    assert result.exit_code == 0
    assert "claude-sonnet-4-6" in result.stdout


def test_cli_record_appends_to_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "usage.jsonl"
    result = runner.invoke(
        app,
        [
            "record",
            "--provider",
            "anthropic",
            "--model",
            "claude-sonnet-4-6",
            "--input-tokens",
            "1000",
            "--output-tokens",
            "500",
            "--feature",
            "pr-review",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert out.is_file()
    line = out.read_text(encoding="utf-8").strip().splitlines()[0]
    data = json.loads(line)
    assert data["model"] == "claude-sonnet-4-6"
    assert data["feature"] == "pr-review"
    # 1000 in @ $3/1M = 3 micros + 500 out @ $15/1M = 7 micros (rounded down) = 10
    assert data["cost_micros"] >= 10


def test_cli_record_warns_for_unknown_model_but_succeeds(tmp_path: Path) -> None:
    out = tmp_path / "usage.jsonl"
    result = runner.invoke(
        app,
        [
            "record",
            "--provider",
            "anthropic",
            "--model",
            "claude-zzz-9000",  # not in price table
            "--input-tokens",
            "100",
            "--output-tokens",
            "50",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert "no price" in result.stdout.lower() or "warning" in result.stdout.lower()


def test_cli_report_writes_artifacts(tmp_path: Path, sample_usage: list[TokenUsage]) -> None:
    usage_file = tmp_path / "usage.jsonl"
    for u in sample_usage:
        append(usage_file, u)

    result = runner.invoke(
        app,
        [
            "report",
            "--from-file",
            str(usage_file),
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    json_path = tmp_path / ".tokencost" / "report.json"
    md_path = tmp_path / ".tokencost" / "report.md"
    assert json_path.is_file()
    assert md_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.0.1"
    assert data["total_calls"] == 4


def test_schema_version_stays_pinned_to_0_0_1() -> None:
    """Schema is stable at 0.0.1 even though tool version moves
    forward -- shape is unchanged, only behavior added."""
    assert SCHEMA_VERSION == "0.0.1"


# ---------------------------------------------------------------------------
# v0.0.2: SDK middlewares (Anthropic + OpenAI) + attribution context
# ---------------------------------------------------------------------------


def test_attribution_merges_nested_blocks() -> None:
    """Inner attribution overrides outer, but only the keys it sets."""
    from tokencost.attribution import attribution, current

    with attribution(feature="outer-feature", environment="prod"):
        assert current() == {"feature": "outer-feature", "environment": "prod"}
        with attribution(actor="acme"):
            # outer feature/env still active; actor newly scoped
            snap = current()
            assert snap["feature"] == "outer-feature"
            assert snap["environment"] == "prod"
            assert snap["actor"] == "acme"
        # Inner block exited -> actor gone
        assert current() == {"feature": "outer-feature", "environment": "prod"}
    # All cleared
    assert current() == {}


def test_attribution_inner_can_override_outer_feature() -> None:
    from tokencost.attribution import attribution, current

    with attribution(feature="outer", actor="alice"), attribution(feature="inner"):
        snap = current()
        assert snap["feature"] == "inner"  # inner wins
        assert snap["actor"] == "alice"  # outer preserved


# ---- Anthropic middleware --------------------------------------------------


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _AnthropicResponse:
    def __init__(
        self, *, model: str, input_tokens: int, output_tokens: int, msg_id: str = "msg_1"
    ) -> None:
        self.id = msg_id
        self.model = model
        self.usage = _Usage(input_tokens, output_tokens)


class _FakeAnthropicMessages:
    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self._response


class _FakeAnthropic:
    def __init__(self, response: object) -> None:
        self.messages = _FakeAnthropicMessages(response)


def test_anthropic_wrap_records_token_usage_with_defaults(tmp_path: Path) -> None:
    """The middleware records one TokenUsage row per successful call."""
    from tokencost.middleware import default_sink
    from tokencost.middleware.anthropic import wrap as anthropic_wrap

    out = tmp_path / "usage.jsonl"
    real = _FakeAnthropic(
        _AnthropicResponse(model="claude-sonnet-4-6", input_tokens=2000, output_tokens=400)
    )
    client = anthropic_wrap(
        real,
        feature="pr-review",
        environment="prod",
        actor="customer:acme",
        sink=default_sink(out),
    )

    response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024)
    assert response.id == "msg_1"
    # The proxy passed kwargs to the real client unchanged.
    assert real.messages.calls[0]["model"] == "claude-sonnet-4-6"

    # One row written, with all wrap-time defaults applied.
    rows = list(_load_usage(out))
    assert len(rows) == 1
    row = rows[0]
    assert row.feature == "pr-review"
    assert row.environment == "prod"
    assert row.actor == "customer:acme"
    assert row.model == "claude-sonnet-4-6"
    assert row.input_tokens == 2000
    assert row.output_tokens == 400
    # Sonnet $3 in / $15 out per 1M -> 2000 in = 6 cents; 400 out = 6 cents.
    # In micro-USD: 6_000 + 6_000 = 12_000.
    assert row.cost_micros == 6_000 + 6_000


def test_anthropic_wrap_uses_attribution_context_to_override(tmp_path: Path) -> None:
    """The attribution() context manager overrides wrap-time defaults."""
    from tokencost.attribution import attribution
    from tokencost.middleware import default_sink
    from tokencost.middleware.anthropic import wrap as anthropic_wrap

    out = tmp_path / "usage.jsonl"
    real = _FakeAnthropic(
        _AnthropicResponse(model="claude-haiku-4-5", input_tokens=1000, output_tokens=200)
    )
    client = anthropic_wrap(real, feature="default-feature", sink=default_sink(out))

    with attribution(feature="search", actor="globex"):
        client.messages.create(model="claude-haiku-4-5")

    rows = list(_load_usage(out))
    assert rows[0].feature == "search"  # context wins over wrap default
    assert rows[0].actor == "globex"


def test_anthropic_wrap_does_not_eat_recording_errors(tmp_path: Path) -> None:
    """A misbehaving sink must NOT break the SDK call."""
    from tokencost.middleware.anthropic import wrap as anthropic_wrap

    real = _FakeAnthropic(
        _AnthropicResponse(model="claude-sonnet-4-6", input_tokens=10, output_tokens=10)
    )

    def boom_sink(_u: object) -> None:
        raise RuntimeError("disk full")

    captured: list[Exception] = []
    client = anthropic_wrap(
        real,
        sink=boom_sink,
        on_error=captured.append,
    )
    response = client.messages.create(model="claude-sonnet-4-6")
    assert response is not None
    assert len(captured) == 1
    assert isinstance(captured[0], RuntimeError)


def test_anthropic_wrap_passes_through_unknown_attributes() -> None:
    """Anything we didn't intercept (e.g. .with_options()) reaches the real client."""
    from tokencost.middleware.anthropic import wrap as anthropic_wrap

    class _RealWithExtra:
        def __init__(self) -> None:
            self.messages = _FakeAnthropicMessages(
                _AnthropicResponse(model="claude-sonnet-4-6", input_tokens=1, output_tokens=1)
            )

        def with_options(self, **kwargs: object) -> str:
            return f"opted: {kwargs!r}"

    proxy = anthropic_wrap(_RealWithExtra(), sink=lambda _u: None)
    assert proxy.with_options(timeout=10).startswith("opted:")


def test_anthropic_wrap_rejects_non_client_objects() -> None:
    from tokencost.middleware.anthropic import wrap as anthropic_wrap

    with pytest.raises(TypeError):
        anthropic_wrap("not a client")


# ---- OpenAI middleware -----------------------------------------------------


class _OpenAIChatUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _OpenAIResponsesUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _OpenAIResponse:
    def __init__(self, model: str, usage: object, msg_id: str = "rsp_1") -> None:
        self.id = msg_id
        self.model = model
        self.usage = usage


class _FakeOpenAILeaf:
    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self._response


class _FakeOpenAIChat:
    def __init__(self, completions: _FakeOpenAILeaf) -> None:
        self.completions = completions


class _FakeOpenAI:
    def __init__(
        self,
        *,
        chat_response: object | None = None,
        responses_response: object | None = None,
    ) -> None:
        if chat_response is not None:
            self.chat = _FakeOpenAIChat(_FakeOpenAILeaf(chat_response))
        if responses_response is not None:
            self.responses = _FakeOpenAILeaf(responses_response)


def test_openai_wrap_records_chat_completions(tmp_path: Path) -> None:
    """Chat completions path: extracts prompt_tokens / completion_tokens."""
    from tokencost.middleware import default_sink
    from tokencost.middleware.openai import wrap as openai_wrap

    out = tmp_path / "usage.jsonl"
    fake = _FakeOpenAI(
        chat_response=_OpenAIResponse(
            model="gpt-5",
            usage=_OpenAIChatUsage(prompt_tokens=1500, completion_tokens=500),
        ),
    )
    client = openai_wrap(fake, feature="search", sink=default_sink(out))

    client.chat.completions.create(model="gpt-5")
    rows = list(_load_usage(out))
    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "openai"
    assert row.model == "gpt-5"
    assert row.input_tokens == 1500
    assert row.output_tokens == 500
    # gpt-5 $10 in / $30 out per 1M -> 1500 * 10 / 1M = 15_000 micro-USD
    # plus 500 * 30 / 1M = 15_000 -> total 30_000.
    assert row.cost_micros == 15_000 + 15_000


def test_openai_wrap_records_responses_api(tmp_path: Path) -> None:
    """Responses API path: extracts input_tokens / output_tokens directly."""
    from tokencost.middleware import default_sink
    from tokencost.middleware.openai import wrap as openai_wrap

    out = tmp_path / "usage.jsonl"
    fake = _FakeOpenAI(
        responses_response=_OpenAIResponse(
            model="gpt-5-mini",
            usage=_OpenAIResponsesUsage(input_tokens=2000, output_tokens=300),
        ),
    )
    client = openai_wrap(fake, sink=default_sink(out))
    client.responses.create(model="gpt-5-mini", input="hello")

    rows = list(_load_usage(out))
    assert len(rows) == 1
    row = rows[0]
    assert row.input_tokens == 2000
    assert row.output_tokens == 300


def test_openai_wrap_rejects_non_client() -> None:
    from tokencost.middleware.openai import wrap as openai_wrap

    with pytest.raises(TypeError):
        openai_wrap(object())


def test_default_sink_writes_to_jsonl(tmp_path: Path) -> None:
    """The default sink is a JSONL appender."""
    from tokencost.middleware import default_sink

    out = tmp_path / "tokens.jsonl"
    sink = default_sink(out)
    sink(
        TokenUsage(
            timestamp=datetime(2026, 5, 8, 12, tzinfo=UTC),
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=1,
            output_tokens=1,
            cost_micros=1,
        )
    )
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "claude-sonnet-4-6" in text


def test_tokencost_version_is_valid_semver() -> None:
    """Don't hardcode the version -- bumps shouldn't need test edits."""
    import re as _re

    from tokencost import __version__

    assert _re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", __version__) is not None


# Helper used by middleware tests above
def _load_usage(path: Path) -> list[TokenUsage]:
    from tokencost.store import load

    return list(load(path))


# ---------------------------------------------------------------------------
# v0.0.3: chain() sink combinator + agtrace integration
# ---------------------------------------------------------------------------


def test_chain_runs_all_sinks_in_order(tmp_path: Path) -> None:
    """Three sinks are invoked left-to-right; all see the same TokenUsage."""
    from tokencost.middleware import chain

    seen: list[tuple[str, TokenUsage]] = []

    def s_a(u: TokenUsage) -> None:
        seen.append(("a", u))

    def s_b(u: TokenUsage) -> None:
        seen.append(("b", u))

    def s_c(u: TokenUsage) -> None:
        seen.append(("c", u))

    combined = chain(s_a, s_b, s_c)
    u = TokenUsage(
        timestamp=datetime(2026, 5, 8, 12, tzinfo=UTC),
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=1,
        output_tokens=1,
        cost_micros=1,
    )
    combined(u)
    assert [name for name, _ in seen] == ["a", "b", "c"]
    assert all(usage is u for _, usage in seen)


def test_chain_failure_in_one_sink_does_not_abort_others() -> None:
    """A bad sink is logged + skipped; later sinks still run."""
    from tokencost.middleware import chain

    seen: list[str] = []

    def good_one(_u: TokenUsage) -> None:
        seen.append("good_one")

    def bad(_u: TokenUsage) -> None:
        raise RuntimeError("disk full")

    def good_two(_u: TokenUsage) -> None:
        seen.append("good_two")

    combined = chain(good_one, bad, good_two)
    combined(
        TokenUsage(
            timestamp=datetime(2026, 5, 8, 12, tzinfo=UTC),
            provider="x",
            model="y",
            input_tokens=1,
            output_tokens=1,
            cost_micros=1,
        )
    )
    assert seen == ["good_one", "good_two"]


def test_to_active_agtrace_span_attaches_cost_to_active_span() -> None:
    """When called inside an agtrace span, the sink writes cost+token
    attributes onto that span. End-to-end cross-product integration."""
    pytest = __import__("pytest")
    pytest.importorskip("agtrace")

    from agtrace.tracer import in_memory_tracer
    from tokencost.middleware import to_active_agtrace_span

    tracer, captured = in_memory_tracer()
    sink = to_active_agtrace_span()

    u = TokenUsage(
        timestamp=datetime(2026, 5, 8, 12, tzinfo=UTC),
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=1234,
        output_tokens=567,
        cost_micros=12_345,
    )
    with tracer.span("llm.call", kind="prompt"):
        sink(u)
    assert len(captured) == 1
    span = captured[0]
    assert span.attributes["tokens.input"] == "1234"
    assert span.attributes["tokens.output"] == "567"
    assert span.attributes["tokens.total"] == "1801"
    assert span.attributes["cost.micros"] == "12345"
    assert span.attributes["cost.usd"].startswith("$0.01")
    assert span.attributes["llm.provider"] == "anthropic"
    assert span.attributes["llm.model"] == "claude-sonnet-4-6"


def test_to_active_agtrace_span_silent_when_no_span_active() -> None:
    """Outside a span block the sink is a no-op (no error)."""
    pytest = __import__("pytest")
    pytest.importorskip("agtrace")

    from tokencost.middleware import to_active_agtrace_span

    sink = to_active_agtrace_span()
    sink(
        TokenUsage(
            timestamp=datetime(2026, 5, 8, 12, tzinfo=UTC),
            provider="x",
            model="y",
            input_tokens=1,
            output_tokens=1,
            cost_micros=1,
        )
    )
    # No assertion needed -- the test passes when the sink doesn't raise.


def test_chain_combines_jsonl_and_agtrace_sinks(tmp_path: Path) -> None:
    """The integration story: write to JSONL on disk AND annotate the active span."""
    pytest = __import__("pytest")
    pytest.importorskip("agtrace")

    from agtrace.tracer import in_memory_tracer
    from tokencost.middleware import chain, default_sink, to_active_agtrace_span

    out = tmp_path / "usage.jsonl"
    tracer, captured = in_memory_tracer()
    sink = chain(default_sink(out), to_active_agtrace_span())

    u = TokenUsage(
        timestamp=datetime(2026, 5, 8, 12, tzinfo=UTC),
        provider="anthropic",
        model="claude-haiku-4-5",
        input_tokens=100,
        output_tokens=50,
        cost_micros=350,
    )
    with tracer.span("agent.run", kind="agent"), tracer.span("llm.call", kind="prompt"):
        sink(u)

    # JSONL file got the row
    rows = list(_load_usage_at(out))
    assert len(rows) == 1
    assert rows[0].cost_micros == 350

    # Active (innermost) span got the attributes
    inner = captured[0]
    assert inner.name == "llm.call"
    assert inner.attributes["llm.model"] == "claude-haiku-4-5"

    # Outer span did NOT get the attributes (sink fired during inner)
    outer = captured[1]
    assert outer.name == "agent.run"
    assert "llm.model" not in outer.attributes


def _load_usage_at(path: Path) -> list[TokenUsage]:
    from tokencost.store import load

    return list(load(path))
