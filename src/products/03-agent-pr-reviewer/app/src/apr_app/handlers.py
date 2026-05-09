"""Pull-request event handler.

Flow:

  pull_request.{opened, synchronize, reopened, ready_for_review} ->
    fetch PR title + body + head SHA via GitHub API                ->
    list changed files                                              ->
    for each file (capped at max_changed_files), download content
      via Contents API and write to a temp dir                     ->
    run apr.engine.review() against the temp dir                   ->
    format the ReviewReport as Markdown                            ->
    upsert a sticky comment on the PR                              ->
    return 200 with a small JSON status body.

Anything else (push, issue_comment, ...) returns 200 with status=ignored.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from apr.engine import review as apr_review
from apr.models import ReviewReport

from apr_app.auth import GitHubAppAuth, auth_from_settings
from apr_app.config import Settings
from apr_app.github import GitHubClient

logger = logging.getLogger(__name__)


HANDLED_PR_ACTIONS: frozenset[str] = frozenset(
    {"opened", "synchronize", "reopened", "ready_for_review"}
)


# Severity-rank table -- used to pick the headline outcome label.
_SEV_RANK: dict[str, int] = {
    "info": 0,
    "warning": 1,
    "error": 2,
    "critical": 3,
}


def _verdict_emoji(report: ReviewReport) -> str:
    """One emoji that summarizes the review outcome at a glance."""
    if report.stats.critical > 0:
        return "🛑"
    if report.stats.error > 0:
        return "❌"
    if report.stats.warning > 0:
        return "⚠️"
    if report.stats.info > 0:
        return "ℹ️"  # noqa: RUF001 - deliberate emoji
    return "✅"


def _format_comment(report: ReviewReport, marker: str, max_rows: int = 30) -> str:
    """Format a ReviewReport as a sticky Markdown comment for a PR.

    Layout:
      - hidden marker (so the next run can find + update this comment)
      - headline with emoji + severity counts
      - findings table (top max_rows entries)
      - footer with tool version + schema
    """
    s = report.stats
    lines: list[str] = [marker, ""]
    lines.append(f"### {_verdict_emoji(report)} Agent-PR Reviewer")
    lines.append("")
    lines.append(
        f"**Findings:** {s.total} total · "
        f"{s.critical} critical · {s.error} error · "
        f"{s.warning} warning · {s.info} info"
    )
    if s.blocking > 0:
        lines.append("")
        lines.append(f"> **{s.blocking} blocking finding(s)** — consider addressing before merge.")
    lines.append("")

    if not report.findings:
        lines.append("_No findings. Nice work._")
    else:
        lines.append("| Severity | File | Line | Rule | Message |")
        lines.append("|---|---|---:|---|---|")
        for f in report.findings[:max_rows]:
            file_disp = f"`{f.file}`" if f.file else "_(repo-level)_"
            line_disp = str(f.line) if f.line else ""
            msg = f.message.replace("|", "\\|")
            lines.append(f"| `{f.severity}` | {file_disp} | {line_disp} | `{f.rule_id}` | {msg} |")
        if len(report.findings) > max_rows:
            lines.append(
                f"| _... and {len(report.findings) - max_rows} more in the full report_ |  |  |  |  |"
            )

    lines.append("")
    lines.append("---")
    lines.append(
        f"_Posted by apr-app · engine v{report.tool_version} · "
        f"schema {report.schema_version} · "
        f"changed files: {len(report.inputs.changed_files)}_"
    )
    return "\n".join(lines)


def _extract_owner_repo(payload: dict[str, Any]) -> tuple[str, str] | None:
    repo = payload.get("repository")
    if not isinstance(repo, dict):
        return None
    full_name = repo.get("full_name")
    if not isinstance(full_name, str) or "/" not in full_name:
        return None
    owner, name = full_name.split("/", 1)
    return owner, name


def _extract_pr_meta(payload: dict[str, Any]) -> tuple[int, str, str | None, str | None] | None:
    """Return (pr_number, head_sha, title, body) or None when the payload
    doesn't carry the fields we need."""
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return None
    n = pr.get("number")
    head = pr.get("head")
    if not isinstance(n, int) or not isinstance(head, dict):
        return None
    sha = head.get("sha")
    if not isinstance(sha, str):
        return None
    title = pr.get("title") if isinstance(pr.get("title"), str) else None
    body = pr.get("body") if isinstance(pr.get("body"), str) else None
    return n, sha, title, body


def _extract_installation_id(payload: dict[str, Any]) -> str | None:
    inst = payload.get("installation")
    if not isinstance(inst, dict):
        return None
    iid = inst.get("id")
    if isinstance(iid, int):
        return str(iid)
    if isinstance(iid, str) and iid.isdigit():
        return iid
    return None


# Files whose extension we know how to grade (matches apr.rules dispatcher).
_KNOWN_EXTS: frozenset[str] = frozenset({".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})


async def _materialize_pr_files(
    gh: GitHubClient,
    owner: str,
    repo: str,
    head_sha: str,
    file_rows: list[dict[str, Any]],
    workdir: Path,
    settings: Settings,
) -> list[str]:
    """Download each changed file's content into `workdir` and return the
    list of relative POSIX paths actually materialized (skips deletions,
    binary blobs, oversized files).
    """
    materialized: list[str] = []
    for row in file_rows:
        path = row.get("filename")
        status = row.get("status", "modified")
        if not isinstance(path, str) or not path:
            continue
        # GitHub uses "removed" for deleted files; nothing to download.
        if status == "removed":
            continue
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext not in _KNOWN_EXTS:
            # apr's per-file rules wouldn't fire for this anyway.
            continue
        try:
            data = await gh.get_file_content(owner, repo, path, ref=head_sha)
        except Exception:
            logger.exception("failed to fetch contents of %s", path)
            continue
        if data is None:
            continue
        if len(data) > settings.max_file_bytes:
            continue
        target = workdir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        materialized.append(path)
    return materialized


async def handle_pull_request(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Run apr.engine.review for a `pull_request` webhook payload."""
    action = payload.get("action")
    if not isinstance(action, str) or action not in HANDLED_PR_ACTIONS:
        return {"status": "ignored", "reason": f"action={action!r} not handled"}

    owner_repo = _extract_owner_repo(payload)
    pr_meta = _extract_pr_meta(payload)
    if owner_repo is None or pr_meta is None:
        return {"status": "error", "reason": "incomplete payload"}
    owner, repo = owner_repo
    pr_number, head_sha, pr_title, pr_body = pr_meta

    # --- token resolution: App auth preferred, PAT as dev fallback ----
    token: str | None = None
    auth_app: GitHubAppAuth | None = auth_from_settings(settings)
    if auth_app is not None:
        installation_id = _extract_installation_id(payload)
        if installation_id is None:
            return {
                "status": "skipped",
                "reason": "App auth configured but webhook had no installation.id",
            }
        try:
            token = await auth_app.installation_token(installation_id)
        except Exception as exc:
            logger.exception("Failed to mint installation token")
            return {"status": "error", "reason": f"auth: {exc!r}"}
    elif settings.github_token is not None:
        token = settings.github_token.get_secret_value()

    if token is None:
        return {
            "status": "skipped",
            "reason": (
                "no auth configured: set APR_APP_APP_ID + "
                "APR_APP_PRIVATE_KEY_PEM (production) or "
                "APR_APP_GITHUB_TOKEN (dev)"
            ),
        }

    # --- gather data, run apr, post comment ---------------------------
    workdir = Path(tempfile.mkdtemp(prefix="apr-app-"))
    try:
        async with GitHubClient(
            token=token,
            base_url=settings.github_api_url,
            timeout=settings.request_timeout_seconds,
        ) as gh:
            try:
                file_rows = await gh.list_pr_files(owner, repo, pr_number)
            except Exception as exc:
                logger.exception("GitHub list_pr_files failed")
                return {"status": "error", "reason": f"list_pr_files: {exc!r}"}

            if len(file_rows) > settings.max_changed_files:
                # Metadata-only review for huge PRs.
                report = apr_review(
                    workdir,
                    [],
                    pr_title=pr_title,
                    pr_description=pr_body,
                )
                note = (
                    f"PR has {len(file_rows)} changed files which exceeds "
                    f"max_changed_files={settings.max_changed_files}. "
                    "Per-file rules were skipped; metadata rules ran."
                )
                logger.info(note)
            else:
                materialized = await _materialize_pr_files(
                    gh, owner, repo, head_sha, file_rows, workdir, settings
                )
                report = apr_review(
                    workdir,
                    materialized,
                    pr_title=pr_title,
                    pr_description=pr_body,
                )

            body = _format_comment(report, settings.sticky_comment_marker)

            try:
                existing = await gh.find_sticky_comment(
                    owner, repo, pr_number, settings.sticky_comment_marker
                )
                if existing is None:
                    await gh.create_comment(owner, repo, pr_number, body)
                    action_taken = "created"
                else:
                    await gh.update_comment(owner, repo, existing, body)
                    action_taken = "updated"
            except Exception as exc:
                logger.exception("Failed to upsert sticky comment")
                return {"status": "error", "reason": f"comment: {exc!r}"}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    s = report.stats
    return {
        "status": "ok",
        "action": action_taken,
        "total": s.total,
        "critical": s.critical,
        "error": s.error,
        "warning": s.warning,
        "info": s.info,
        "blocking": s.blocking,
    }
