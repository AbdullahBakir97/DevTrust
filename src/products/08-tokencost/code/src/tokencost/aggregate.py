"""Aggregate TokenUsage rows into a CostReport.

We compute the total + four breakdowns (feature / model / environment /
actor). Each breakdown is sorted by cost descending so the most
expensive rows show up at the top of the report.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from tokencost import __version__
from tokencost.models import Bucket, CostReport, TokenUsage


@dataclass
class _Acc:
    """Mutable accumulator used while summing. Frozen Bucket is built last."""

    label: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micros: int = 0

    def add(self, usage: TokenUsage) -> None:
        self.calls += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cost_micros += usage.cost_micros

    def freeze(self) -> Bucket:
        return Bucket(
            label=self.label,
            calls=self.calls,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost_micros=self.cost_micros,
        )


def _sorted_buckets(accs: dict[str, _Acc]) -> list[Bucket]:
    """Freeze accumulators and sort by cost desc, breaking ties by label."""
    buckets = [a.freeze() for a in accs.values()]
    buckets.sort(key=lambda b: (-b.cost_micros, b.label))
    return buckets


def aggregate(rows: Iterable[TokenUsage]) -> CostReport:
    """Build a `CostReport` from an iterable of `TokenUsage` rows.

    Empty input produces a valid report with all zeros and an empty
    window. Operators downstream treat that as 'no usage in scope'.
    """
    by_feature: dict[str, _Acc] = {}
    by_model: dict[str, _Acc] = {}
    by_env: dict[str, _Acc] = {}
    by_actor: dict[str, _Acc] = {}

    total_calls = 0
    total_in = 0
    total_out = 0
    total_cost = 0

    earliest: datetime | None = None
    latest: datetime | None = None

    for u in rows:
        total_calls += 1
        total_in += u.input_tokens
        total_out += u.output_tokens
        total_cost += u.cost_micros

        if earliest is None or u.timestamp < earliest:
            earliest = u.timestamp
        if latest is None or u.timestamp > latest:
            latest = u.timestamp

        feature_key = u.feature or "(unset)"
        model_key = u.model
        env_key = u.environment or "(unset)"
        actor_key = u.actor or "(unset)"

        by_feature.setdefault(feature_key, _Acc(label=feature_key)).add(u)
        by_model.setdefault(model_key, _Acc(label=model_key)).add(u)
        by_env.setdefault(env_key, _Acc(label=env_key)).add(u)
        by_actor.setdefault(actor_key, _Acc(label=actor_key)).add(u)

    now = datetime.now(UTC)
    return CostReport(
        generated_at=now,
        tool_version=__version__,
        window_start=earliest or now,
        window_end=latest or now,
        total_calls=total_calls,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cost_micros=total_cost,
        by_feature=_sorted_buckets(by_feature),
        by_model=_sorted_buckets(by_model),
        by_environment=_sorted_buckets(by_env),
        by_actor=_sorted_buckets(by_actor),
    )
