"""Shared pytest fixtures for whychanged tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from whychanged.models import Change


@pytest.fixture
def now() -> datetime:
    """A fixed reference time so tests don't drift with the real clock."""
    return datetime(2026, 5, 8, 14, 30, 0, tzinfo=UTC)


@pytest.fixture
def sample_changes(now: datetime) -> list[Change]:
    """A spread of changes across a 2-hour window with mixed kinds."""
    return [
        Change(
            kind="deploy",
            source="git",
            timestamp=now - timedelta(minutes=2),
            summary="Tighten validation in models",
            actor="abdullah",
            files=["src/api/models.py"],
        ),
        Change(
            kind="config",
            source="argocd",
            timestamp=now - timedelta(minutes=8),
            summary="Bump replica count from 3 to 6",
            actor="oncall-bot",
            files=["k8s/api/deployment.yaml"],
        ),
        Change(
            kind="dependency",
            source="renovate",
            timestamp=now - timedelta(minutes=45),
            summary="Bump httpx 0.27 -> 0.28",
            actor="renovate[bot]",
            files=["pyproject.toml", "uv.lock"],
        ),
        Change(
            kind="feature-flag",
            source="launchdarkly",
            timestamp=now - timedelta(hours=8),
            summary="Enable new-checkout for 100% of US traffic",
            actor="pm@example.com",
        ),
    ]


@pytest.fixture
def empty_repo(tmp_path: Path) -> Iterator[Path]:
    """A tmp_path that is NOT a git repo. Used to verify GitChangeProvider
    degrades gracefully when there's nothing to read."""
    yield tmp_path
