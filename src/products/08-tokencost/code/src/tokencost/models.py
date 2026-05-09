"""Pydantic models for TokenCost.

The schema in this file is the public API. Exporters, dashboards, and
finance integrations read this shape. Treat changes as breaking.
Versioned via `CostReport.schema_version`.

All money is represented in **micro-USD** (1 USD = 1,000,000 micro)
because Python floats can't represent fractional cents accurately and
finance teams care about the third and fourth decimal place when
aggregating millions of rows. The Markdown report renders dollars; the
JSON keeps the raw integer micros for downstream math.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.0.1"

# 1 USD in micro-USD. Use this constant in all currency-conversion code
# so the magic number doesn't drift.
MICROS_PER_USD = 1_000_000


# ---------------------------------------------------------------------------
# Usage events
# ---------------------------------------------------------------------------

CallStatus = Literal["ok", "error", "rate-limited", "timeout"]


class TokenUsage(BaseModel):
    """One LLM call worth of usage data.

    Designed to be cheap enough to record on every call. Apps emit one
    `TokenUsage` per request; the store persists it; the aggregator
    rolls it up later.

    `cost_micros` is the canonical money column. It's denormalized from
    the price table so historical reports survive future price changes
    -- a call that cost $0.0042 in May 2026 still reads as $0.0042 in
    May 2027 even if Anthropic raises Sonnet pricing.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    provider: str = Field(
        ...,
        description="LLM provider id: 'anthropic', 'openai', 'bedrock', ...",
    )
    model: str = Field(
        ...,
        description="Model id at call time (e.g. 'claude-sonnet-4-6').",
    )
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cost_micros: int = Field(
        ...,
        ge=0,
        description="Total cost in micro-USD (1e-6 USD).",
    )

    # Attribution dimensions -- all optional. Apps populate the ones
    # they care about for finance breakdowns.
    feature: str | None = Field(
        default=None,
        description="Product feature this call served (e.g. 'pr-review').",
    )
    environment: str | None = Field(
        default=None,
        description="Deploy environment (e.g. 'prod', 'staging').",
    )
    actor: str | None = Field(
        default=None,
        description="User / customer / team this call was for.",
    )
    request_id: str | None = Field(
        default=None,
        description="Stable identifier so the same request isn't double-counted.",
    )

    status: CallStatus = "ok"


# ---------------------------------------------------------------------------
# Aggregation result
# ---------------------------------------------------------------------------


class Bucket(BaseModel):
    """One row in a breakdown (by-feature, by-model, by-actor, etc.)."""

    model_config = ConfigDict(frozen=True)

    label: str
    calls: int = Field(..., ge=0)
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cost_micros: int = Field(..., ge=0)

    @property
    def cost_usd(self) -> float:
        """Convenience for human display. Don't use for further math."""
        return self.cost_micros / MICROS_PER_USD


class CostReport(BaseModel):
    """The full cost-attribution report.

    JSON layout:    `.tokencost/report.json`
    Human companion: `.tokencost/report.md`
    """

    model_config = ConfigDict(frozen=False)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    tool_version: str

    window_start: datetime
    window_end: datetime

    total_calls: int = Field(..., ge=0)
    total_input_tokens: int = Field(..., ge=0)
    total_output_tokens: int = Field(..., ge=0)
    total_cost_micros: int = Field(..., ge=0)

    by_feature: list[Bucket] = Field(default_factory=list)
    by_model: list[Bucket] = Field(default_factory=list)
    by_environment: list[Bucket] = Field(default_factory=list)
    by_actor: list[Bucket] = Field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return self.total_cost_micros / MICROS_PER_USD


# ---------------------------------------------------------------------------
# Budget alerts (forward-compatible -- v0.0.2 adds enforcement)
# ---------------------------------------------------------------------------


AlertKind = Literal["budget-exceeded", "burn-rate-elevated", "anomaly"]


class BudgetAlert(BaseModel):
    """A condition the operator wants flagged in CI / dashboards / paging."""

    model_config = ConfigDict(frozen=True)

    kind: AlertKind
    label: str = Field(
        ...,
        description="Human-readable scope (e.g. 'feature=pr-review' or 'monthly-total').",
    )
    threshold_micros: int = Field(..., ge=0)
    actual_micros: int = Field(..., ge=0)
    message: str
