"""Read a list of changed files from one of three sources.

Supported inputs (in priority order — first match wins):
  1. CLI: explicit `--changed FILE [FILE ...]`
  2. A unified diff file: `--diff path/to/changes.diff`
  3. A plain text file with one path per line
  4. Auto-detect via `git diff --name-only HEAD~1` if a git repo is present

Each source returns a normalized list of POSIX-style paths relative to
the repo root. We do NOT resolve renames (git's `R100` rename markers) -
we treat both old and new names as changed, which is the safe choice for
test selection.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# `diff --git a/path/one b/path/two` -- captures "two" (the new name).
_DIFF_GIT_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
# `+++ b/path/file` (the post-image, our "new" file)
_DIFF_PLUSPLUS_RE = re.compile(r"^\+\+\+ b/(.+)$")
# `--- a/path/file` (the pre-image, the "old" file)
_DIFF_MINUSMINUS_RE = re.compile(r"^--- a/(.+)$")


def _normalize(path: str, repo_root: Path) -> str:
    """Return a POSIX-style path relative to repo root."""
    p = path.replace("\\", "/").strip()
    # If the input is absolute, make it relative.
    pp = Path(p)
    if pp.is_absolute():
        try:
            pp = pp.relative_to(repo_root.resolve())
        except ValueError:
            return pp.as_posix()
    return pp.as_posix()


def from_cli_args(paths: list[str], repo_root: Path) -> list[str]:
    """Direct list from the user."""
    return [_normalize(p, repo_root) for p in paths if p.strip()]


def from_unified_diff(diff_text: str, repo_root: Path) -> list[str]:
    """Parse a unified diff and return the set of files that changed.

    Both pre- and post-image paths are returned (deduplicated). When the
    `--- /dev/null` or `+++ /dev/null` lines appear (add/delete), they are
    skipped silently.
    """
    seen: set[str] = set()
    for raw in diff_text.splitlines():
        m = _DIFF_GIT_HEADER_RE.match(raw)
        if m:
            seen.add(_normalize(m.group(1), repo_root))
            seen.add(_normalize(m.group(2), repo_root))
            continue
        m = _DIFF_MINUSMINUS_RE.match(raw)
        if m and m.group(1) != "/dev/null":
            seen.add(_normalize(m.group(1), repo_root))
            continue
        m = _DIFF_PLUSPLUS_RE.match(raw)
        if m and m.group(1) != "/dev/null":
            seen.add(_normalize(m.group(1), repo_root))
            continue
    return sorted(seen)


def from_path_list_file(text: str, repo_root: Path) -> list[str]:
    """Plain text: one path per line. Blank lines and `#` comments ignored."""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(_normalize(line, repo_root))
    return out


def from_git_auto(repo_root: Path) -> list[str] | None:
    """Try `git diff --name-only HEAD` then `HEAD~1..HEAD`.

    Returns None if git isn't available or the directory isn't a repo;
    callers can then fall back to "no narrow selection possible".
    """
    if not (repo_root / ".git").exists():
        return None
    for args in (
        ["git", "-C", str(repo_root), "diff", "--name-only", "HEAD"],
        ["git", "-C", str(repo_root), "diff", "--name-only", "HEAD~1..HEAD"],
    ):
        try:
            out = subprocess.run(args, capture_output=True, text=True, check=False, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out.returncode == 0:
            paths = [
                _normalize(line, repo_root) for line in out.stdout.splitlines() if line.strip()
            ]
            if paths:
                return sorted(set(paths))
    return None
