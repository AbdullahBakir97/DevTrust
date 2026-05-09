"""TokenCost - financial-grade attribution for LLM spend.

When the CFO asks "what did our AI features cost us last month, broken
down by feature / team / customer cohort?", engineering should have a
crisp answer. TokenCost is the system of record that makes that
boardroom-grade reporting possible:

  - One typed model for usage events (`TokenUsage`).
  - A versioned per-model price table.
  - A JSONL log store you can dump from any backend.
  - An aggregator that produces totals + breakdowns by feature, model,
    actor, and time bucket.
  - Markdown + JSON reports tuned for finance review.

v0.0.1 focuses on the data plane. SDK middlewares (one-line install
for the OpenAI / Anthropic clients) and the hosted dashboard land in
v0.0.2+.
"""

__version__ = "0.0.3"
