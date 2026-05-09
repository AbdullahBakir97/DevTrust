"""Pydantic models for WhyChanged.

The schema in this file is the public API. CI integrations and external
consumers read this shape. Treat changes as breaking. Versioned via
`IncidentReport.schema_version`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.0.1"


# ---------------------------------------------------------------------------
# Changes
# ---------------------------------------------------------------------------

ChangeKind = Literal[
    "deploy",  # commit-on-main, container release, cloud build
    "feature-flag",  # LaunchDarkly / Statsig / homegrown flag toggle
    "config",  # Kubernetes ConfigMap, env-var change, infra apply
    "dependency",  # package.json / requirements update, image bump
    "schema",  # database migration / schema change
    "unknown",
]


class Change(BaseModel):
    """One observed change in the production environment."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    source: str = Field(
        ...,
        description=(
            "Identifier for the provider that observed this change "
            "(e.g. 'git', 'launchdarkly', 'argocd')."
        ),
    )
    timestamp: datetime
    summary: str = Field(
        ...,
        description="One-line human-readable summary suitable for a list view.",
    )
    actor: str | None = Field(
        default=None,
        description="Person or system that made the change, when known.",
    )
    files: list[str] = Field(
        default_factory=list,
        description=(
            "Repo-relative POSIX paths affected by this change. Empty "
            "for changes that don't have a meaningful file scope."
        ),
    )
    url: str | None = Field(
        default=None,
        description="Link back to the change source (commit, PR, flag).",
    )


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class RankedChange(BaseModel):
    """A Change with WhyChanged's culprit-likelihood score + reasoning."""

    model_config = ConfigDict(frozen=True)

    change: Change
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Higher = more likely to be the culprit.",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description=(
            "Human-readable signals that contributed to the score "
            "(e.g. 'within 5 minutes of incident', 'touches affected service')."
        ),
    )


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


class ChangeWindow(BaseModel):
    """The time window the report covered."""

    model_config = ConfigDict(frozen=True)

    incident_at: datetime | None = Field(
        default=None,
        description=(
            "The incident's start time. When None, the report covers a "
            "rolling window ending at `generated_at`."
        ),
    )
    since: datetime
    until: datetime


class IncidentReport(BaseModel):
    """The full report emitted by `whychanged explain`.

    JSON layout:    `.whychanged/report.json`
    Human companion: `.whychanged/report.md`
    """

    model_config = ConfigDict(frozen=False)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    tool_version: str

    service: str | None = Field(
        default=None,
        description="The service / repo / scope this report is about.",
    )
    window: ChangeWindow
    ranked: list[RankedChange] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.ranked)

    @property
    def top_culprit(self) -> RankedChange | None:
        return self.ranked[0] if self.ranked else None
