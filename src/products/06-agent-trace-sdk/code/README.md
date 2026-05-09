# Agent Trace SDK (`agtrace`)

> Agent-aware tracing. Spans, events, and tool calls for LLM-driven workflows.

## Why

Generic OpenTelemetry models web servers and database calls. AI agents need a different shape: prompts, tool calls, retries, fallbacks. `agtrace` borrows OTel's span tree but specializes the kind taxonomy so traces remain useful for debugging agents.

`agtrace` is the data primitive that `apr-app` and (eventually) `sts-app` will emit telemetry into — one trace per PR review, one span per LLM call, one span per tool invocation, all stitched together.

## Status

**v0.0.1 alpha.** In-process tracer + JSONL exporter + CLI dump. OTLP / Jaeger / hosted-collector exporters land in v0.1+.

## What v0.0.1 ships

- `agtrace.tracer.Tracer` with a context-manager API.
- Span kinds tuned for AI workloads: `agent` · `prompt` · `tool_call` · `retry` · `fallback` · `unknown`.
- Automatic trace tree (parent / child via `ContextVar` — works under asyncio + threads).
- Exception handling: an exception inside a span sets `status="error"` and records the exception type as an attribute. The exception still propagates.
- Configurable exporter: default JSONL appender; `in_memory_tracer()` for tests; bring-your-own callable for OTLP / Sentry / Datadog.
- CLI: `agtrace dump --from-file traces.jsonl` pretty-prints a trace tree.

## Usage

```python
from agtrace import default_tracer

tracer = default_tracer()      # writes to .agtrace/traces.jsonl

with tracer.span("agent.run", kind="agent", attributes={"agent": "pr-reviewer"}):
    with tracer.span("llm.call", kind="prompt") as s:
        s.set_attribute("model", "claude-sonnet-4-6")
        s.set_attribute("max_tokens", 1024)
        # ... call your LLM here ...
        s.add_event("rate-limited", attributes={"retry_after": "1.5"})

    with tracer.span("tool.call", kind="tool_call") as s:
        s.set_attribute("tool", "read_file")
        # ... run the tool ...
```

```bash
agtrace version
agtrace dump --from-file .agtrace/traces.jsonl
# Renders a Rich tree:
#   agent.run (agent)  (124ms)
#     agent=pr-reviewer
#     llm.call (prompt)  (98ms)
#       model=claude-sonnet-4-6
#     tool.call (tool_call)  (12ms)
#       tool=read_file
```

## Roadmap

- **v0.1** — `OtlpExporter` (OTLP/HTTP) so traces ship into Honeycomb / Grafana / Datadog.
- **v0.1** — context propagation across HTTP boundaries (`agtrace.propagation`).
- **v0.2** — sampling + rate-limiting for production volume.
- **v0.3** — integration with `tokencost` so each `prompt` span carries the cost in its attributes natively.

## Apache-2.0 license. See [CHANGELOG](CHANGELOG.md).
