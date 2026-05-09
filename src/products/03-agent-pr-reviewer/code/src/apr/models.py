"""Pydantic models for the Agent-PR Reviewer.

The schema in this file is the public API of `apr`. Downstream consumers
(the GitHub App that posts comments, dashboards, anyone reading
`.apr/review.json`) read this shape. Treat changes as breaking.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.0.1"


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

Severity = Literal["info", "warning", "error", "critical"]

Category = Literal[
    "quality",  # general code-quality smells
    "security",  # potentially unsafe patterns
    "style",  # convention / readability nits
    "ai-pattern",  # signs of AI-generated boilerplate or hallucinations
    "todo",  # TODO / FIXME / XXX bookkeeping
    "commit",  # commit-message issues (when `apr` is fed commit data)
]


class Finding(BaseModel):
    """One reviewer finding tied to a file and (optionally) a line."""

    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(
        ...,
        description=(
            "Stable identifier for the rule that produced this finding "
            "(e.g. 'bare-except', 'todo-no-ticket', 'pr-description-too-short')."
        ),
    )
    severity: Severity
    category: Category
    message: str
    file: str | None = Field(
        default=None,
        description="Repo-relative POSIX path. None for repo-level findings.",
    )
    line: int | None = Field(default=None, ge=1)
    suggestion: str | None = Field(
        default=None,
        description="Optional human-readable suggested fix.",
    )


# ---------------------------------------------------------------------------
# Review report
# ---------------------------------------------------------------------------


class ReviewInputs(BaseModel):
    """The inputs the reviewer saw -- captured for reproducibility."""

    model_config = ConfigDict(frozen=True)

    repo_root: str
    changed_files: list[str] = Field(default_factory=list)
    pr_title: str | None = None
    pr_description: str | None = None


class ReviewStats(BaseModel):
    """Aggregate counts useful for terminal display + CI gates."""

    model_config = ConfigDict(frozen=True)

    info: int = Field(..., ge=0)
    warning: int = Field(..., ge=0)
    error: int = Field(..., ge=0)
    critical: int = Field(..., ge=0)

    @property
    def total(self) -> int:
        return self.info + self.warning + self.error + self.critical

    @property
    def blocking(self) -> int:
        """Findings severe enough that a CI gate should stop the merge."""
        return self.error + self.critical


class ReviewReport(BaseModel):
    """The full report emitted by `apr review`.

    JSON layout:    `.apr/review.json`
    Human companion: `.apr/review.md`
    """

    model_config = ConfigDict(frozen=False)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    tool_version: str

    inputs: ReviewInputs
    stats: ReviewStats
    findings: list[Finding] = Field(default_factory=list)
