"""Change providers - sources of "what happened in production".

A `ChangeProvider` answers one question: "what changes did your system
see between `since` and `until`?" v0.0.1 ships one concrete provider:

  - `GitChangeProvider`  reads `git log` for commits in the window.
                         A commit is treated as an implicit deploy when
                         the consumer's CI/CD ships from main.

Future providers (v0.1+):

  - `GitHubDeploymentsProvider`   -- GitHub Deployments API
  - `LaunchDarklyProvider`        -- flag-toggle audit log
  - `RenderDeploymentsProvider`   -- service deploy events
  - `VercelDeploymentsProvider`   -- preview / production deploys
  - `KubernetesEventsProvider`    -- Apply / restart events
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Protocol

from whychanged.models import Change

logger = logging.getLogger(__name__)


class ChangeProvider(Protocol):
    """Anything that can list Changes in a time window."""

    name: str

    def changes(self, since: datetime, until: datetime) -> list[Change]:
        """Return every Change observed in `[since, until]`.

        Implementations MUST be side-effect-free other than outbound
        I/O. They MUST handle their own credentials and rate limits;
        the engine treats provider exceptions as "no changes" and
        continues with the rest.
        """
        ...


# ---------------------------------------------------------------------------
# GitChangeProvider
# ---------------------------------------------------------------------------


# Format string for `git log`. Fields are tab-separated so we can split
# without escaping concerns. The trailing %x00 isn't strictly needed but
# makes commit-boundary detection trivial when extending later.
_GIT_LOG_FORMAT = "%H%x09%aI%x09%an%x09%s"


class GitChangeProvider:
    """Read commits from a git repo as implicit deploy Changes.

    Why this is a sensible v0.0.1 default:
      - Every consumer already has git, so no network or auth setup
        is required to see useful output.
      - For teams that ship from main on merge, a commit IS the deploy
        unit; no separate deploy provider is needed for v0.0.1.
      - Once the team adopts WhyChanged seriously, they wire in real
        deploy events via a provider plugin and this becomes the
        always-available baseline.
    """

    name = "git"

    def __init__(
        self,
        repo_root: Path,
        *,
        branch: str | None = None,
        max_commits: int = 200,
    ) -> None:
        self.repo_root = repo_root
        self.branch = branch
        self.max_commits = max_commits

    def changes(self, since: datetime, until: datetime) -> list[Change]:
        """Return one Change per commit in `[since, until]` on the chosen branch."""
        if shutil.which("git") is None:
            logger.warning("git binary not on PATH; GitChangeProvider returns []")
            return []
        if not (self.repo_root / ".git").exists() and not (self.repo_root / "HEAD").exists():
            logger.debug("no .git in %s; GitChangeProvider returns []", self.repo_root)
            return []

        args = [
            "git",
            "-C",
            str(self.repo_root),
            "log",
            f"--since={since.isoformat()}",
            f"--until={until.isoformat()}",
            f"--pretty=format:{_GIT_LOG_FORMAT}",
            "--name-only",
            f"--max-count={self.max_commits}",
        ]
        if self.branch:
            args.append(self.branch)

        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("git log failed: %s", exc)
            return []
        if proc.returncode != 0:
            logger.debug("git log returned %d: %s", proc.returncode, proc.stderr.strip())
            return []

        return _parse_git_log(proc.stdout)


def _parse_git_log(raw: str) -> list[Change]:
    """Parse the output of `git log --pretty=format:... --name-only`.

    Each commit appears as:

        <sha>\t<iso-date>\t<author-name>\t<subject>\n
        path/to/file\n
        path/to/another\n
        \n   (blank line separating commits, except possibly the last)

    Robust to missing trailing newlines and empty commits (no files).
    """
    changes: list[Change] = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        header = lines[i]
        i += 1
        if not header or "\t" not in header:
            continue
        parts = header.split("\t", 3)
        if len(parts) != 4:
            continue
        _sha, iso_date, author, subject = parts
        try:
            ts = datetime.fromisoformat(iso_date)
        except ValueError:
            continue

        files: list[str] = []
        while i < len(lines) and lines[i].strip():
            # Rely on tab presence to detect the next header line. Header
            # lines start with a 40-char SHA followed by \t.
            line = lines[i]
            if (
                "\t" in line
                and len(line.split("\t", 1)[0]) >= 7
                and " " not in line.split("\t", 1)[0]
            ):
                # This looks like the next commit's header; stop.
                break
            files.append(line)
            i += 1
        # Skip the blank separator line if present
        while i < len(lines) and not lines[i].strip():
            i += 1

        changes.append(
            Change(
                kind="deploy",
                source="git",
                timestamp=ts,
                summary=subject,
                actor=author or None,
                files=files,
                url=None,
            )
        )
    return changes
