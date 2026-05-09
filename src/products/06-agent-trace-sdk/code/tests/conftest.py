"""Shared fixtures for agtrace tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from agtrace.tracer import Tracer, in_memory_tracer


@pytest.fixture
def captured_tracer() -> Iterator[tuple[Tracer, list]]:
    """Yields (tracer, captured-spans-list). The list grows as spans close."""
    tracer, captured = in_memory_tracer()
    yield tracer, captured


@pytest.fixture
def jsonl_path(tmp_path: Path) -> Path:
    return tmp_path / "traces.jsonl"
