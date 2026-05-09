# tokencost - changelog

All notable changes to `tokencost` are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.0.3] - 2026-05-08

### Added
- **Sink combinator** `tokencost.middleware.chain(*sinks)` -- runs every sink for each TokenUsage event, isolated against individual sink failures (a crashing sink is logged but does NOT prevent later sinks from running).
- **`tokencost.middleware.to_active_agtrace_span()`** -- cross-product integration sink. When the recording call happens inside an `agtrace` span block, the sink pins these attributes on that span:
  - `tokens.input`, `tokens.output`, `tokens.total`
  - `cost.micros`, `cost.usd` (formatted dollar string)
  - `llm.provider`, `llm.model`
  Result: one trace shows BOTH what the agent did AND what each LLM call cost.
  Gracefully no-ops when `agtrace` isn't installed (the import fails silently and the sink becomes a stub).
- 6 new tests: chain runs all sinks in order, chain isolates per-sink failures, agtrace integration end-to-end (cost + token + model attributes attached to the right span), silent no-op when no span is active, the canonical pattern (`chain(default_sink(), to_active_agtrace_span())`) writes to JSONL AND annotates the active span, version assertion.

### Notes
- Schema unchanged (still 0.0.1). Version bump 0.0.2 -> 0.0.3.
- The pattern is now: one client wrap, one sink chain. Everything else is configuration.
- `agtrace` is NOT a hard dependency of `tokencost` -- the integration is opt-in. You install both packages and call `to_active_agtrace_span()`. If you only install `tokencost`, that function still works and just no-ops.

### Canonical setup (Anthropic + agtrace)

```python
from anthropic import Anthropic
from agtrace import default_tracer
from tokencost.attribution import attribution
from tokencost.middleware import chain, default_sink, to_active_agtrace_span
from tokencost.middleware.anthropic import wrap as wrap_anthropic

tracer = default_tracer()
client = wrap_anthropic(
    Anthropic(),
    sink=chain(default_sink(), to_active_agtrace_span()),
)

with tracer.span("agent.run", kind="agent"):
    with tracer.span("llm.call", kind="prompt"):
        with attribution(feature="pr-review", actor="customer:acme"):
            client.messages.create(model="claude-sonnet-4-6", ...)
            # -> appended to .tokencost/usage.jsonl
            # -> tokens.input / tokens.output / cost.usd pinned on llm.call span
```

[0.0.3]: https://github.com/AbdullahBakir97/tokencost/compare/v0.0.2...v0.0.3

---

## [0.0.2] - 2026-05-08

### Added
- **SDK middlewares.** One-line auto-recording for the major LLM SDKs:
  - `tokencost.middleware.anthropic.wrap(client, ...)` -- proxies an `anthropic.Anthropic` client. Every successful `client.messages.create(...)` call records a `TokenUsage` event with the model, token counts, computed cost, and attribution (feature / environment / actor / request_id).
  - `tokencost.middleware.openai.wrap(client, ...)` -- proxies an `openai.OpenAI` client. Supports both the **Chat Completions** path (`client.chat.completions.create`, reads `prompt_tokens` / `completion_tokens`) and the **Responses API** (`client.responses.create`, reads `input_tokens` / `output_tokens`).
- **Per-call attribution context** (`tokencost.attribution.attribution(...)` ContextVar-based context manager). Lets the same wrapped client serve multiple features: outer block sets defaults, inner block overrides any field. Composes correctly across asyncio + threads + nested spans.
- **Configurable sink interface** (`Sink = Callable[[TokenUsage], None]`). Default is `default_sink(path)` which appends to a JSONL file. Operators with high volume swap in their own callback (queue producer, Redis publisher, structured logger).
- **on_error callback** for sink failures. The middleware ships exception-isolated -- a sink that crashes never breaks the user's SDK call. Errors are logged and optionally forwarded to the user-supplied callback.
- **Pass-through proxy semantics.** Anything we didn't intercept (e.g. `client.with_options(...)`, `client.beta.*`) falls through to the real client unchanged. Drop-in safe.
- 13 new tests: nested attribution merging, override semantics, Anthropic wrap with defaults, Anthropic attribution-context override, Anthropic sink-error isolation, Anthropic pass-through proxy, Anthropic non-client rejection, OpenAI Chat Completions path, OpenAI Responses API path, OpenAI non-client rejection, default sink writes JSONL, schema/version assertions.

### Notes
- Schema unchanged (still 0.0.1). Just version bump 0.0.1 -> 0.0.2 on `tokencost`.
- The middlewares duck-type the SDK response objects and do **not** import `anthropic` / `openai` -- tokencost still installs cleanly without those wheels. Tests use lightweight fakes.
- Async clients (`AsyncAnthropic`, `AsyncOpenAI`) are deferred to v0.0.3 alongside streaming-aware recording.

[0.0.2]: https://github.com/AbdullahBakir97/tokencost/compare/v0.0.1...v0.0.2

---

## [0.0.1] - 2026-05-08

### Added
- Initial scaffold: `tokencost` Python package with three CLI commands (`record`, `report`, `prices`, plus `version`).
- Pydantic v2 schema (versioned 0.0.1): `TokenUsage`, `Bucket`, `CostReport`, `BudgetAlert`. All money carried as integer micro-USD (`cost_micros`) to avoid float drift across millions of rows.
- `prices` module: per-model price table (Anthropic Claude Opus 4.6 / Sonnet 4.6 / Haiku 4.5; OpenAI GPT-5 / GPT-5-mini, May 2026 rates). Operator escape hatch via `add_model()` for runtime overrides.
- `store` module: append-only JSONL log with tolerant loader (skips malformed lines + lines that fail Pydantic validation, with logging).
- `aggregate` module: rolls a stream of TokenUsage rows into a CostReport with four breakdowns (by feature, by model, by environment, by actor), each sorted by cost descending. Empty input produces a valid zero-report.
- `output` module: JSON + Markdown writers emitting to `.tokencost/report.{json,md}`. Markdown is finance-tuned (dollars to 2dp, sub-cent to 4dp).
- 22 smoke tests covering: known-model lookup, integer-arithmetic price calculator, runtime price overrides, JSONL round-trip, malformed-line tolerance, aggregator totals + breakdowns + sort order + window detection, CLI commands (record / report / prices / version), schema-version alignment.
- Apache-2.0 license, hatchling build, typer/rich/pydantic deps.

### Notes
- Wave 3 revenue product. Replaces the patchwork of "ad-hoc CSV + Excel" most teams use today.
- Money is **always micro-USD on disk**. The price table uses micro-USD per million tokens. Rendering to dollars happens only in the Markdown report and CLI output.
- The Anthropic / OpenAI SDK middlewares (one-line auto-record on every call) are deliberately deferred to v0.0.2 — getting the data shape right is more important than a polished SDK wrapper.

[0.0.1]: https://github.com/AbdullahBakir97/tokencost/releases/tag/v0.0.1
