"""Pydantic models for the Smart Test Selector.

The schema in this file *is* the public API of `sts`. CI integrations and
downstream tools (DevTrust dashboards, the future GitHub App) read this shape.
Treat changes to it as breaking. Versioned via `SelectionReport.schema_version`.

History
-------
- 0.0.1 - initial schema.
- 0.1.0 - adds optional `RepoxArtifact` (used when sts loads
          `.repox/architecture.json`) and `repox_artifact` field on
          `SelectionInputs`. Old readers ignore the new field.
- 0.2.0 - extends `RepoxArtifact` with `imports_by_source` -- the
          file -> in-repo-targets map used by the transitive-import
          affecting heuristic. Non-breaking (defaults to `{}`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Bump only when the schema breaks downstream readers.
SCHEMA_VERSION = "0.2.0"


# ---------------------------------------------------------------------------
# Test reference & framework
# ---------------------------------------------------------------------------

TestFramework = Literal[
    "pytest",
    "jest",
    "vitest",
    "mocha",
    "gotest",
    "cargo",
    "unknown",
]

TestKind = Literal["unit", "integration", "e2e", "unknown"]


class TestRef(BaseModel):
    """A single test file the selector saw."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(..., description="Path relative to repo root, POSIX-style.")
    framework: TestFramework = "unknown"
    kind: TestKind = "unknown"


# ---------------------------------------------------------------------------
# Selection result
# ---------------------------------------------------------------------------

# must  - reach for the change directly; skipping risks shipping a broken build
# should - we couldn't prove relevance, but couldn't prove non-relevance either
# skip   - we have positive evidence this test is unaffected (rare in v0.0.1)
SelectionPriority = Literal["must", "should", "skip"]


class TestSelection(BaseModel):
    """One test's selection verdict and why."""

    model_config = ConfigDict(frozen=True)

    test: TestRef
    priority: SelectionPriority
    reason: str = Field(
        ...,
        description=(
            "Human-readable justification. e.g. 'sibling test in same directory', "
            "'manifest changed', 'naming-convention match for src/foo.py'."
        ),
    )


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------


class SelectionInputs(BaseModel):
    """The inputs the selector saw — captured for reproducibility."""

    model_config = ConfigDict(frozen=True)

    repo_root: str
    changed_files: list[str] = Field(default_factory=list)
    diff_source: Literal["cli", "diff-file", "git-auto", "stdin"] = "cli"
    used_repox_artifact: bool = False


class SelectionStats(BaseModel):
    """Aggregate counts useful for terminal display and CI logging."""

    model_config = ConfigDict(frozen=True)

    total_tests_in_repo: int = Field(..., ge=0)
    must_run: int = Field(..., ge=0)
    should_run: int = Field(..., ge=0)
    can_skip: int = Field(..., ge=0)

    @property
    def selected(self) -> int:
        """Count of tests recommended for execution (must + should)."""
        return self.must_run + self.should_run


class SelectionReport(BaseModel):
    """The full report emitted by `sts select`.

    JSON layout:    `.sts/selection.json`
    Human companion: `.sts/selection.md`
    """

    model_config = ConfigDict(frozen=False)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    tool_version: str

    inputs: SelectionInputs
    stats: SelectionStats
    selections: list[TestSelection]

    # When True, the engine fell back to "run everything" because of a
    # high-impact change (manifest, lockfile, config). UI can highlight this.
    fallback_run_all: bool = False
    fallback_reason: str | None = None


# ---------------------------------------------------------------------------
# Repo X-ray integration (new in 0.1.0)
# ---------------------------------------------------------------------------


class RepoxArtifact(BaseModel):
    """Subset of the Repo X-ray artifact that sts cares about.

    Captured in the SelectionReport so a selection can be replayed from
    the same architecture data later.
    """

    model_config = ConfigDict(frozen=True)

    paths: list[str] = Field(default_factory=list)
    schema_version: str = "unknown"
    tool_version: str = "unknown"
    incompatible_schema: bool = False
    # source_file -> [in-repo target paths]. Empty when the artifact
    # is a v0.0.x or v0.1.x repox build (no call graph yet) or when
    # the analyzed repo has no Python / JS / TS source.
    imports_by_source: dict[str, list[str]] = Field(default_factory=dict)
