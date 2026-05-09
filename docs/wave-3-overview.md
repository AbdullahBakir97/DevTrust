# Wave 3 — the AI-era observability layer

> Three small, opinionated tools that answer the three questions every SRE asks during an AI-era incident:
> **What changed? · What did it cost? · What did the agent do?**

DevTrust's Wave 3 isn't another monitoring dashboard. The dashboard market is saturated. What's missing is a narrow, _correctly-shaped_ set of primitives that turn AI-system incidents into solvable problems instead of mysteries.

## The three questions, mapped

| Question | Tool | Headline output |
|---|---|---|
| **What changed?** | `whychanged` | Ranked list of recent changes (deploys, flag toggles, config diffs, dep bumps) most likely to have caused the incident. |
| **What did it cost?** | `tokencost` | Per-feature, per-actor, per-model breakdown of LLM spend with finance-grade integer money math. |
| **What did the agent do?** | `agtrace` | Span tree of the agent run — every prompt, every tool call, every retry — with parent-child relationships. |

Each tool ships standalone. The interesting story is what happens when they're wired together.

## The integration

`tokencost` and `agtrace` agree on one shape: an "active span" you can attach attributes to. When `tokencost` records a usage event _inside_ an `agtrace` span block, the cost lands directly on the span — same trace, same hierarchy, same dump output.

```
agent.run (agent) (4ms)
├── agent=pr-reviewer
└── llm.call (prompt) (3ms)
    ├── model=claude-sonnet-4-6
    ├── tokens.input=1234
    ├── tokens.output=567
    ├── tokens.total=1801
    ├── cost.micros=12000
    ├── cost.usd=$0.0120
    ├── llm.provider=anthropic
    └── llm.model=claude-sonnet-4-6
```

**One trace = the agent's work AND its cost.**

## The canonical setup (~10 lines of code)

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
    with tracer.span("llm.call", kind="prompt"), attribution(feature="pr-review", actor="customer:acme"):
        client.messages.create(model="claude-sonnet-4-6", ...)
        # -> appended to .tokencost/usage.jsonl
        # -> tokens.input / tokens.output / cost.usd pinned on llm.call span
```

Three lines of imports, one wrapped client, one chained sink. Everything else is application code.

## Why each tool is sized this way

### `whychanged` is small on purpose

It's not a deployment platform. It's not a feature-flag system. It's a **ranking heuristic** that takes a stream of "things happened" events from any source you care to plug in and sorts them by likelihood of being the culprit, given a time window and a service scope.

- v0.0.1 ships with one provider — the local Git log — because that's the universal lowest common denominator.
- v0.1+ adds cloud providers (`GitHubDeploymentsProvider`, `LaunchDarklyProvider`, `RenderDeploymentsProvider`).
- The ranking is intentionally deterministic so it can be regression-tested against historical incidents. v0.2 replaces it with a learned model once there's outcome data.

### `tokencost` is finance-grade on purpose

Existing LLM-cost tools (Helicone, Langfuse) touch this but neither is what a CFO would call _the system of record_. `tokencost`:

- Carries money in **integer micro-USD** (`cost_micros`) end-to-end. Floating-point cents drift over millions of rows; integers don't.
- Denormalizes price at call time — a call that cost $0.0042 in May 2026 still reads as $0.0042 in May 2027 even if Anthropic raises Sonnet pricing.
- Ships a JSONL store and SDK middlewares. **No new database to operate.** Operators already have a log pipeline; tokencost ships into it.

### `agtrace` is purpose-built on purpose

Generic OpenTelemetry models web servers and database calls. The span kinds are `server` / `client` / `internal`. That's not the shape of an AI agent.

`agtrace` ships kinds that reflect what AI systems actually do — `agent`, `prompt`, `tool_call`, `retry`, `fallback` — and gets out of the way otherwise. Span IDs are the same width as OpenTelemetry's, so the same trace can graduate to a generic OTel collector with one exporter swap when you're ready.

## What this is NOT

- **Not a hosted service.** The Wave 3 trio is libraries + CLIs you run inside your stack. The hosted dashboard play is later, after the open-source layer is widely adopted.
- **Not a replacement for Datadog / Grafana / Sentry.** Those tell you a request is slow or a service is down. The Wave 3 trio tells you _why_ in AI-system terms.
- **Not coupled.** Each tool stands alone. The wiring is opt-in: a one-line sink that no-ops if the other tool isn't installed.

## Status — May 2026

| Package | Version | Status |
|---|---|---|
| `whychanged` | v0.0.1 | alpha — Git provider only; cloud providers in v0.1 |
| `tokencost`  | v0.0.3 | alpha — Anthropic + OpenAI middlewares + agtrace integration |
| `agtrace`    | v0.0.2 | alpha — JSONL exporter + cross-product hooks |

All three pass `mypy --strict` + `ruff check` + `ruff format --check`. Apache-2.0. Public PyPI release pending — the release tooling at `scripts/release.py` + `.github/workflows/release.yml` handles tag-driven publishes via PyPI Trusted Publishing.

## Where this fits in the broader DevTrust thesis

Wave 1 (`repox` + `sts` + `sts-app`) is the **trust layer for AI-augmented development**: codebase architecture model, smart test selection, sticky PR comments.

Wave 2 (`apr` + `apr-app`) is the **review layer**: deterministic + LLM-backed PR review.

Wave 3 (`whychanged` + `tokencost` + `agtrace`) is the **observability layer**: when something goes wrong in production, these three answer the questions you need answered.

Together they form **the trust stack for AI-era engineering — from PR to production.**

## Try it

```bash
# Install (workspace developer mode, until PyPI release):
git clone https://github.com/AbdullahBakir97/DevTrust
cd DevTrust
uv sync --all-packages --all-groups

# Each tool's own README has its standalone CLI. The integrated demo:
python -c "
from agtrace import default_tracer
from tokencost.middleware import chain, default_sink, to_active_agtrace_span
from tokencost.models import TokenUsage
from datetime import datetime, UTC

tracer = default_tracer()
sink = chain(default_sink(), to_active_agtrace_span())

with tracer.span('agent.run', kind='agent', attributes={'agent': 'demo'}):
    with tracer.span('llm.call', kind='prompt') as s:
        s.set_attribute('model', 'claude-sonnet-4-6')
        sink(TokenUsage(
            timestamp=datetime.now(UTC),
            provider='anthropic', model='claude-sonnet-4-6',
            input_tokens=1234, output_tokens=567, cost_micros=12000,
            feature='demo',
        ))
"
agtrace dump --from-file .agtrace/traces.jsonl
```

That's the whole story.
