"""Shared pytest fixtures for tokencost tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tokencost.models import TokenUsage


@pytest.fixture
def sample_usage() -> list[TokenUsage]:
    """A spread of usage rows across features, models, environments, actors."""
    base = datetime(2026, 5, 8, 14, 0, 0, tzinfo=UTC)
    return [
        TokenUsage(
            timestamp=base,
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=200_000,
            cost_micros=3_000_000 + 3_000_000,  # $3 in + $3 out -> $6 total
            feature="pr-review",
            environment="prod",
            actor="customer:acme",
        ),
        TokenUsage(
            timestamp=base + timedelta(minutes=10),
            provider="anthropic",
            model="claude-haiku-4-5",
            input_tokens=500_000,
            output_tokens=100_000,
            cost_micros=500_000 + 500_000,  # $0.50 in + $0.50 out -> $1
            feature="test-selection",
            environment="prod",
            actor="customer:acme",
        ),
        TokenUsage(
            timestamp=base + timedelta(minutes=20),
            provider="openai",
            model="gpt-5",
            input_tokens=200_000,
            output_tokens=50_000,
            cost_micros=2_000_000 + 1_500_000,  # $2 + $1.50 -> $3.50
            feature="pr-review",
            environment="staging",
            actor="customer:globex",
        ),
        TokenUsage(
            timestamp=base + timedelta(minutes=30),
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=10_000,
            output_tokens=5_000,
            cost_micros=30_000 + 75_000,  # ~$0.10
            feature=None,  # unset on purpose -> aggregator should put it in '(unset)'
            environment="dev",
            actor=None,
        ),
    ]
