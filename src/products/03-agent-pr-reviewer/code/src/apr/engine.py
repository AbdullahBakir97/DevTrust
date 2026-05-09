"""Top-level review orchestration.

The engine takes a repo root, a list of changed files, optional PR
metadata (title + description), and optional AI configuration (provider
+ diff). It runs:

  1. PR-level checks (title, description) -- once per review.
  2. File-level checks for each changed file in a known language.
  3. AI rule pack (apr.rules_ai), gated behind `enable_ai=True`.

Findings are deduplicated and stable-sorted (file, line, severity).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from apr import __version__
from apr.llm import LLMProvider, NullProvider
from apr.models import (
    Finding,
    ReviewInputs,
    ReviewReport,
    ReviewStats,
    Severity,
)
from apr.repox_integration import load as load_repox_artifact
from apr.rules import check_file, check_pr_metadata
from apr.rules_ai import run_ai_rules

_SEVERITY_ORDER: dict[Severity, int] = {
    "info": 0,
    "warning": 1,
    "error": 2,
    "critical": 3,
}


def _stable_key(f: Finding) -> tuple[str, int, int, str]:
    """Stable sort key: file, line, severity rank (asc), rule_id."""
    return (
        f.file or "",
        f.line or 0,
        _SEVERITY_ORDER[f.severity],
        f.rule_id,
    )


def review(
    repo_root: Path,
    changed_files: list[str],
    pr_title: str | None = None,
    pr_description: str | None = None,
    *,
    enable_ai: bool = False,
    llm_provider: LLMProvider | None = None,
    diff: str | None = None,
) -> ReviewReport:
    """Run all checks and produce a ReviewReport.

    AI rules are off by default. Pass `enable_ai=True` AND optionally
    a `llm_provider` (defaults to NullProvider) to enable
    `ai-review:hallucinated-symbol` (deterministic, uses repox call
    graph) and `ai-review:diff-comprehension` (delegates to the
    provider).
    """
    findings: list[Finding] = []

    findings.extend(check_pr_metadata(pr_title, pr_description))
    for rel in changed_files:
        findings.extend(check_file(repo_root, rel))

    if enable_ai:
        artifact = load_repox_artifact(repo_root)
        provider: LLMProvider = llm_provider or NullProvider()
        findings.extend(
            run_ai_rules(
                repo_root,
                changed_files,
                artifact=artifact,
                provider=provider,
                diff=diff,
                pr_title=pr_title,
                pr_description=pr_description,
            )
        )

    findings.sort(key=_stable_key)

    counts: Counter[Severity] = Counter()
    for f in findings:
        counts[f.severity] += 1

    stats = ReviewStats(
        info=counts["info"],
        warning=counts["warning"],
        error=counts["error"],
        critical=counts["critical"],
    )

    return ReviewReport(
        generated_at=datetime.now(UTC),
        tool_version=__version__,
        inputs=ReviewInputs(
            repo_root=str(repo_root),
            changed_files=sorted(changed_files),
            pr_title=pr_title,
            pr_description=pr_description,
        ),
        stats=stats,
        findings=findings,
    )
