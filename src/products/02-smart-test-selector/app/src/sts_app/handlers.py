"""Pull-request event handler.

Flow (v0.0.3):

  pull_request.{opened, synchronize, reopened, ready_for_review} ->
    list changed files via GitHub API                        ->
    if enable_full_review:                                    ->
        download tarball at PR head SHA, extract to tempdir   ->
        run repox.analyzer.analyze() against the tempdir      ->
        run sts.selector.select() with the resulting artifact ->
    else (or on full-review failure):                         ->
        list repo tree via Tree API (v0.0.2 fallback)         ->
        run sts.selector.select() against the file list only  ->
    format the SelectionReport as Markdown                    ->
    upsert a sticky comment on the PR                         ->
    return 200 with a small JSON status body.

For every other event type we no-op with a 200.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from sts.selector import select as select_engine

from sts_app.auth import GitHubAppAuth, auth_from_settings
from sts_app.config import Settings
from sts_app.github import GitHubClient
from sts_app.review import fetch_clone_and_select

logger = logging.getLogger(__name__)


HANDLED_PR_ACTIONS: frozenset[str] = frozenset(
    {"opened", "synchronize", "reopened", "ready_for_review"}
)


def _format_comment(report: Any, marker: str, max_rows: int = 25) -> str:
    """Format a SelectionReport as a sticky Markdown comment."""
    s = report.stats
    lines: list[str] = [marker, ""]
    lines.append("### Smart Test Selector")
    lines.append("")
    if report.fallback_run_all:
        lines.append(f"**Verdict: run all {s.total_tests_in_repo} tests** (safe-default fallback)")
        if report.fallback_reason:
            lines.append("")
            lines.append(f"_Reason: {report.fallback_reason}_")
    else:
        lines.append(
            f"**Verdict:** {s.must_run} must-run · "
            f"{s.should_run} should-run · "
            f"{s.can_skip} skip · "
            f"({s.total_tests_in_repo} total)"
        )
    lines.append("")

    must = [sel for sel in report.selections if sel.priority == "must"]
    if must:
        lines.append("#### Must-run tests")
        lines.append("")
        lines.append("| Test | Framework | Reason |")
        lines.append("|---|---|---|")
        for sel in must[:max_rows]:
            lines.append(f"| `{sel.test.path}` | {sel.test.framework} | {sel.reason} |")
        if len(must) > max_rows:
            lines.append(f"| _... and {len(must) - max_rows} more (see full report)_ |  |  |")
        lines.append("")

    lines.append("---")
    lines.append(
        f"_Posted by sts-app v{report.tool_version} · "
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


def _extract_pr_number(payload: dict[str, Any]) -> int | None:
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        n = payload.get("number")
        return n if isinstance(n, int) else None
    n = pr.get("number")
    return n if isinstance(n, int) else None


def _extract_head_sha(payload: dict[str, Any]) -> str | None:
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return None
    head = pr.get("head")
    if not isinstance(head, dict):
        return None
    sha = head.get("sha")
    return sha if isinstance(sha, str) else None


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


async def handle_pull_request(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Run the selector for a `pull_request` webhook payload."""
    action = payload.get("action")
    if not isinstance(action, str) or action not in HANDLED_PR_ACTIONS:
        return {"status": "ignored", "reason": f"action={action!r} not handled"}

    owner_repo = _extract_owner_repo(payload)
    pr_number = _extract_pr_number(payload)
    head_sha = _extract_head_sha(payload)
    if owner_repo is None or pr_number is None or head_sha is None:
        return {
            "status": "error",
            "reason": "missing repository / pr number / head sha in payload",
        }
    owner, repo = owner_repo

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
                "no auth configured: set STS_APP_APP_ID + "
                "STS_APP_PRIVATE_KEY_PEM (production) or "
                "STS_APP_GITHUB_TOKEN (dev)"
            ),
        }

    async with GitHubClient(
        token=token,
        base_url=settings.github_api_url,
        timeout=settings.request_timeout_seconds,
    ) as gh:
        try:
            changed = await gh.list_pr_files(owner, repo, pr_number)
        except Exception as exc:
            logger.exception("GitHub list_pr_files failed")
            return {"status": "error", "reason": f"github api: {exc!r}"}

        if len(changed) > settings.max_changed_files:
            return {
                "status": "fallback",
                "reason": (
                    f"changed files {len(changed)} exceeds "
                    f"max_changed_files={settings.max_changed_files}"
                ),
            }

        # v0.0.3 default path: tarball clone -> repox.analyze() -> sts.select().
        # Falls back to v0.0.2 Tree-API path on any clone/analyze failure.
        report = None
        used_full_review = False
        if settings.enable_full_review:
            workdir = Path(tempfile.mkdtemp(prefix="sts-app-"))
            try:
                report = await fetch_clone_and_select(
                    gh._client,
                    owner=owner,
                    repo=repo,
                    head_sha=head_sha,
                    changed_files=changed,
                    workdir=workdir,
                    max_repo_bytes=settings.max_repo_bytes,
                )
                used_full_review = True
            except Exception as exc:
                logger.warning(
                    "Full-review path failed (%s); falling back to Tree API",
                    exc,
                )
                report = None
            finally:
                shutil.rmtree(workdir, ignore_errors=True)

        if report is None:
            try:
                tree = await gh.list_tree(owner, repo, head_sha)
            except Exception as exc:
                logger.exception("GitHub list_tree failed")
                return {"status": "error", "reason": f"github api: {exc!r}"}
            report = select_engine(
                repo_root=Path("/virtual/" + owner + "/" + repo),
                repo_files=tree,
                changed_files=changed,
                diff_source="cli",
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
            logger.exception("Failed to post sticky comment")
            return {"status": "error", "reason": f"comment: {exc!r}"}

    return {
        "status": "ok",
        "action": action_taken,
        "full_review": used_full_review,
        "must_run": report.stats.must_run,
        "should_run": report.stats.should_run,
        "total": report.stats.total_tests_in_repo,
    }
