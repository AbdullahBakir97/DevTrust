"""Shared pytest fixtures for AgentGuard tests."""

from __future__ import annotations

import pytest
from agentguard.models import Policy, Rule


@pytest.fixture
def simple_allow_policy() -> Policy:
    """Allow only `fs.read`, deny everything else (default)."""
    return Policy(
        name="test-simple-allow",
        rules=[
            Rule(
                name="allow-fs-read",
                effect="allow",
                tool="fs.read",
                reason="Reads are safe in this test policy.",
            ),
        ],
    )


@pytest.fixture
def approval_required_policy() -> Policy:
    """Stripe charges require approval; reads pass straight through."""
    return Policy(
        name="test-approval-required",
        rules=[
            Rule(
                name="require-approval-stripe",
                effect="require_approval",
                tool="stripe.*",
                reason="Stripe calls require human approval in this test policy.",
            ),
            Rule(
                name="allow-fs-read",
                effect="allow",
                tool="fs.read",
                reason="Reads are safe.",
            ),
        ],
    )
