"""Top-level WhyChanged orchestration.

Given a time window and a list of providers, the engine:

  1. Asks every provider for changes in the window.
  2. Scores each change with the v0.0.1 ranking heuristic:
       a. Recency relative to the incident time -- changes within the
          5 minutes before the incident score higher than changes 12
          hours earlier.
       b. File-scope match -- when the user passes `service_files`, a
          change that touches any of those files scores higher.
       c. Kind weight -- schema migrations and config changes outscore
          dependency bumps when all else is equal.
  3. Returns a sorted IncidentReport.

Real ML-based ranking lands in v0.2 once we have outcome data ("was the
top-ranked change actually the culprit?"). v0.0.1 is intentionally
deterministic so the output is gradable.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from whychanged import __version__
from whychanged.models import (
    Change,
    ChangeKind,
    ChangeWindow,
    IncidentReport,
    RankedChange,
)
from whychanged.providers import ChangeProvider

logger = logging.getLogger(__name__)


# Heuristic weights -- tuneable knobs. v0.0.1 picks defaults that match
# common SRE intuition; v0.2 will replace these with a learned model.

# How quickly the recency score decays as we move further from the
# incident. 30-minute half-life means a change 30m before the incident
# scores half as much as a change 0m before it.
_RECENCY_HALF_LIFE = timedelta(minutes=30)

_SERVICE_FILE_BONUS = 0.30
_KIND_WEIGHTS: dict[ChangeKind, float] = {
    "schema": 1.00,
    "config": 0.85,
    "deploy": 0.75,
    "dependency": 0.65,
    "feature-flag": 0.70,
    "unknown": 0.50,
}


def _recency_score(
    change_at: datetime,
    incident_at: datetime,
    half_life: timedelta = _RECENCY_HALF_LIFE,
) -> float:
    """Decaying score: 1.0 at the incident moment, halves every half_life.

    Changes AFTER the incident never get a positive score (they didn't
    cause it). Changes far before fade gracefully toward 0.
    """
    delta = incident_at - change_at
    if delta < timedelta(0):
        return 0.0
    half_lives = delta.total_seconds() / half_life.total_seconds()
    # 0.5 ** half_lives approaches 0 as delta grows.
    return float(0.5**half_lives)


def _file_bonus(change_files: list[str], service_files: set[str]) -> tuple[float, str | None]:
    """Bonus + reason text when the change touches any service file."""
    if not service_files:
        return 0.0, None
    overlap = [f for f in change_files if f in service_files]
    if not overlap:
        return 0.0, None
    sample = overlap[0]
    extra = f" (+{len(overlap) - 1} more)" if len(overlap) > 1 else ""
    return _SERVICE_FILE_BONUS, f"touches `{sample}`{extra}"


def _score_change(
    c: Change,
    incident_at: datetime,
    service_files: set[str],
) -> RankedChange:
    """Compute the score and reason list for one change."""
    reasons: list[str] = []

    recency = _recency_score(c.timestamp, incident_at)
    reasons.append(_describe_recency(c.timestamp, incident_at))

    file_bonus, file_reason = _file_bonus(c.files, service_files)
    if file_reason is not None:
        reasons.append(file_reason)

    kind_weight = _KIND_WEIGHTS.get(c.kind, 0.5)
    reasons.append(f"kind weight: {c.kind} ({kind_weight:.2f})")

    # Combine: recency dominates, file bonus stacks, kind weight modulates.
    # Cap at 1.0 because Pydantic enforces it.
    score = min(1.0, (recency + file_bonus) * kind_weight)
    return RankedChange(change=c, score=score, reasons=reasons)


def _describe_recency(change_at: datetime, incident_at: datetime) -> str:
    delta = incident_at - change_at
    if delta < timedelta(0):
        return f"{abs(delta)} after incident (excluded by recency)"
    if delta < timedelta(minutes=5):
        return f"{int(delta.total_seconds() // 60) or 0}m before incident"
    if delta < timedelta(hours=1):
        return f"{int(delta.total_seconds() // 60)}m before incident"
    if delta < timedelta(days=1):
        return f"{int(delta.total_seconds() // 3600)}h before incident"
    return f"{delta.days}d before incident"


def explain(
    *,
    repo_root: Path,
    providers: Sequence[ChangeProvider],
    since: datetime | None = None,
    until: datetime | None = None,
    incident_at: datetime | None = None,
    service: str | None = None,
    service_files: set[str] | None = None,
    window: timedelta = timedelta(minutes=30),
) -> IncidentReport:
    """Build an IncidentReport from the supplied providers.

    Defaults:
      - `until`        defaults to now (UTC).
      - `since`        defaults to `until - window` (or `incident_at - window`).
      - `incident_at`  defaults to `until` (rolling-window mode).

    `service_files` is an optional allow-list of repo-relative paths
    that belong to the affected service; changes touching one of them
    score higher.
    """
    now = datetime.now(UTC)
    until = until or now
    if since is None:
        anchor = incident_at or until
        since = anchor - window
    incident_at = incident_at or until
    files_set = service_files or set()

    all_changes: list[Change] = []
    for provider in providers:
        try:
            all_changes.extend(provider.changes(since, until))
        except Exception:
            logger.exception("provider %r raised; skipping", getattr(provider, "name", provider))
            continue

    ranked = [_score_change(c, incident_at, files_set) for c in all_changes]
    ranked.sort(key=lambda r: r.score, reverse=True)

    return IncidentReport(
        generated_at=now,
        tool_version=__version__,
        service=service,
        window=ChangeWindow(
            incident_at=incident_at,
            since=since,
            until=until,
        ),
        ranked=ranked,
    )
