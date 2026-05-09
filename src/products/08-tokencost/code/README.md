# TokenCost (`tokencost`)

> Financial-grade attribution for LLM spend. **What did our AI features cost us last month, broken down by feature, team, and customer cohort?**

## Why

Every CFO is asking "how much are we spending on AI?" and engineering can't answer cleanly. Bills swing 2–3× per quarter unexpectedly. Existing tools (Helicone, Langfuse) touch this but neither is finance-grade.

TokenCost is the system of record:
- **Typed schema** so downstream finance integrations don't break.
- **Money in micro-USD integers** so floating-point rounding doesn't accumulate over millions of rows.
- **Append-only JSONL store** that ships well with any log pipeline.
- **Aggregator** that produces the four breakdowns finance always wants.

## Status

**v0.0.1 alpha** — data plane only. SDK middlewares (one-line install for OpenAI / Anthropic clients) and the hosted dashboard land in v0.0.2+.

## Money model

| Concept | Unit | Why |
|---|---|---|
| `cost_micros` on every row | micro-USD (integer) | Python `float` can't represent fractional cents accurately — at 10M rows the drift is real money |
| Price table (`prices.py`) | micro-USD per million tokens | Mirrors how Anthropic / OpenAI quote rates |
| Markdown reports | dollars (2dp; 4dp for sub-cent) | Human display only; downstream math always uses micros |

## CLI

```bash
tokencost version
tokencost prices    # list the per-model price table baked into this build

# Record one call (manual entry; SDK middleware comes in v0.0.2)
tokencost record \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --input-tokens 1234 \
  --output-tokens 567 \
  --feature pr-review \
  --environment prod \
  --actor customer:acme

# Aggregate one or more JSONL files into a finance report
tokencost report --from-file .tokencost/usage.jsonl
```

Output: `.tokencost/usage.jsonl` (append-only event log) + `.tokencost/report.{json,md}` (aggregated report).

## Roadmap

- **v0.0.2** — `tokencost.middleware.openai` and `tokencost.middleware.anthropic` (one-line wrap of the SDK client; auto-records every call).
- **v0.0.3** — budget alerts: `tokencost check --budget feature:pr-review=$1000/mo`.
- **v0.1** — hosted multi-tenant dashboard at $0.50 per million tracked-tokens.
- **v0.1** — finance integrations: NetSuite, Sage, QuickBooks export shape.
- **v0.2** — anomaly detection on burn-rate (call out the 2× quarter-over-quarter spike before the CFO asks).

## Apache-2.0 license. See [CHANGELOG](CHANGELOG.md).
