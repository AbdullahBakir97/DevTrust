"""Agent Trace SDK - agent-aware tracing for LLM-driven workflows.

OpenTelemetry's spans + events shape, but specialized for the things
AI agents actually do:

  - prompt span  (system + user messages, model id, max_tokens)
  - tool_call span  (tool name, arguments, return value)
  - retry / fallback events
  - parent / child relationships across nested agent calls

v0.0.1 ships the data model + the in-process tracer + a JSONL exporter.
OTLP / Jaeger exporters land in v0.1+.

Public API:

    from agtrace import Tracer, default_tracer
    from agtrace.attribution import attribution

    tracer = default_tracer()      # JSONL to .agtrace/traces.jsonl
    with tracer.span("agent.run", attributes={"agent": "pr-reviewer"}):
        with tracer.span("llm.call", kind="prompt") as s:
            s.set_attribute("model", "claude-sonnet-4-6")
            ...

`tokencost` and `apr-app` will eventually emit telemetry into this
shape so a single trace shows both \"what the agent did\" and \"what it
cost\".
"""

__version__ = "0.0.2"

from agtrace.tracer import Tracer, default_tracer  # noqa: F401
