"""Orchestrate a full PR review: clone -> repox build -> sts select.

This module stitches together the workspace deps into one async function
the handler can call. Keeping it separate from `handlers.py` makes it
trivial to unit-test the orchestration without spinning up FastAPI.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from sts.models import RepoxArtifact, SelectionReport
from sts.selector import select as sts_select

logger = logging.getLogger(__name__)


def _build_imports_by_source(arch: Any) -> dict[str, list[str]]:
    """Convert an in-memory repox.models.Architecture into the
    `imports_by_source` dict that sts.selector wants.

    Treats `arch` as Any so this module doesn't import repox.models at
    type-checking time -- repox's type stubs are workspace-resolved at
    runtime, but tests can pass a plain stub here.
    """
    out: dict[str, list[str]] = {}
    cg = getattr(arch, "call_graph", None)
    if cg is None:
        return out
    imports = getattr(cg, "imports", [])
    for imp in imports:
        target = getattr(imp, "target_file", None)
        if not isinstance(target, str):
            continue
        src = getattr(imp, "source_file", None)
        if not isinstance(src, str):
            continue
        out.setdefault(src, []).append(target)
    return {k: sorted(set(v)) for k, v in out.items()}


def select_with_full_review(
    repo_root: Path,
    changed_files: list[str],
) -> SelectionReport:
    """Run repox.analyze() against the cloned repo, then sts.select().

    Imported lazily so the test suite can replace `_run_repox_analyze`
    with a stub that doesn't require Python 3.11+ AST features.
    """
    arch = _run_repox_analyze(repo_root)

    raw_paths = [getattr(f, "path", None) for f in getattr(arch, "files", [])]
    repo_files: list[str] = [p for p in raw_paths if isinstance(p, str)]

    imports_by_source = _build_imports_by_source(arch)
    schema_version = getattr(arch, "schema_version", "unknown")
    tool_version = getattr(arch, "tool_version", "unknown")

    artifact = RepoxArtifact(
        paths=sorted(set(repo_files)),
        schema_version=str(schema_version),
        tool_version=str(tool_version),
        incompatible_schema=False,
        imports_by_source=imports_by_source,
    )
    return sts_select(
        repo_root=repo_root,
        repo_files=repo_files,
        changed_files=changed_files,
        diff_source="cli",
        repox_artifact=artifact,
    )


def _run_repox_analyze(repo_root: Path) -> Any:
    """Indirection so tests can monkey-patch this without touching repox.

    Production: imports repox.analyzer lazily and calls analyze().
    """
    # Lazy import keeps repox out of the cold-start path when full review
    # is disabled, and lets tests stub this function.
    from repox.analyzer import analyze

    return analyze(repo_root)


async def fetch_clone_and_select(
    client: httpx.AsyncClient,
    *,
    owner: str,
    repo: str,
    head_sha: str,
    changed_files: list[str],
    workdir: Path,
    max_repo_bytes: int,
) -> SelectionReport:
    """Top-level: download + extract tarball, then run the full review.

    Errors propagate so the caller can decide whether to fall back to
    metadata-only review or surface the error to the operator.
    """
    from sts_app.clone import fetch_and_extract

    cloned_root = await fetch_and_extract(
        client,
        owner,
        repo,
        head_sha,
        workdir,
        max_bytes=max_repo_bytes,
    )
    logger.info(
        "cloned %s/%s@%s into %s (%d changed files)",
        owner,
        repo,
        head_sha[:7],
        cloned_root,
        len(changed_files),
    )
    return select_with_full_review(cloned_root, changed_files)
