"""Top-level orchestration for `repox build`.

In v0.1 this module is deliberately slim - heavy lifting moved into focused
submodules:

  - languages       - extension tables and helpers
  - manifests       - pyproject / package.json / Cargo.toml / go.mod parsing
  - conventions     - light-touch convention extraction (indent, layout, license)

What's still here:
  - .gitignore-aware tree walk
  - language classification (per-file)
  - aggregation into the final Architecture artifact
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import pathspec

from repox import __version__
from repox import callgraph as callgraph_mod
from repox import conventions as conv_mod
from repox import manifests as manifests_mod
from repox.languages import (
    BINARY_EXTS,
    DEFAULT_IGNORE,
    EXT_TO_LANG,
)
from repox.models import (
    Architecture,
    DependencyGraph,
    EntryPoint,
    FileInfo,
    LanguageStats,
    RepoMeta,
)

# ---------------------------------------------------------------------------
# tree walk + classification helpers
# ---------------------------------------------------------------------------


def _read_gitignore(root: Path) -> pathspec.PathSpec[pathspec.Pattern]:
    patterns: list[str] = list(DEFAULT_IGNORE)
    gi = root / ".gitignore"
    if gi.is_file():
        with contextlib.suppress(OSError):
            patterns.extend(gi.read_text(encoding="utf-8", errors="ignore").splitlines())
    # pathspec 1.x uses "gitignore" (the older "gitwildmatch" was deprecated).
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def _is_binary(path: Path, ext: str) -> bool:
    if ext.lower() in BINARY_EXTS:
        return True
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        return b"\0" in chunk
    except OSError:
        return True


def _count_lines(path: Path) -> int | None:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def _walk(root: Path, spec: pathspec.PathSpec[pathspec.Pattern]) -> Iterable[Path]:
    """Yield non-ignored regular files under root."""
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if spec.match_file(rel):
            continue
        yield p


# ---------------------------------------------------------------------------
# entry-point detection
# ---------------------------------------------------------------------------

# Conventional file names that are entry points even when no manifest declares them.
_CONVENTIONAL_ENTRIES: list[tuple[str, str, str | None]] = [
    ("main.py", "cli", "Python main module"),
    ("__main__.py", "cli", "Python -m entrypoint"),
    ("manage.py", "cli", "Django management"),
    ("app.py", "web", "Flask/FastAPI conventional entry"),
    ("server.py", "web", "Generic server entry"),
    ("index.js", "cli", "Node conventional entry"),
    ("index.ts", "cli", "TS conventional entry"),
    ("index.mjs", "cli", "Node ESM conventional entry"),
    ("Dockerfile", "container", "Container build entry"),
    ("Containerfile", "container", "OCI build entry"),
]


def _detect_entry_points(
    root: Path, files: list[FileInfo]
) -> tuple[list[EntryPoint], DependencyGraph]:
    """Combine manifest-declared entry points with conventional-name fallbacks.

    Returns (entry_points, dep_graph). Manifest-declared entries take precedence -
    conventional matches are only added if their path isn't already declared.
    """
    eps, deps, manifests = manifests_mod.parse_all(root)
    declared = {ep.path for ep in eps}
    file_paths = {f.path for f in files}

    for fname, kind, detail in _CONVENTIONAL_ENTRIES:
        if fname in file_paths and fname not in declared:
            eps.append(EntryPoint(path=fname, kind=kind, detail=detail))
            declared.add(fname)

    graph = DependencyGraph(manifests=manifests, dependencies=deps)
    return eps, graph


# ---------------------------------------------------------------------------
# top-level analyze()
# ---------------------------------------------------------------------------


def analyze(root: Path) -> Architecture:
    """Analyze the repo at `root` and produce a full Architecture artifact."""
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    spec = _read_gitignore(root)

    files: list[FileInfo] = []
    lang_acc: dict[str, LanguageStats] = {}
    total_size = 0
    total_lines = 0

    for path in _walk(root, spec):
        ext = path.suffix.lower() or path.name.lower()
        is_binary = _is_binary(path, ext)
        size = path.stat().st_size
        lang = EXT_TO_LANG.get(ext) if not is_binary else None
        lines = _count_lines(path) if not is_binary else None

        rel = path.relative_to(root).as_posix()
        info = FileInfo(
            path=rel,
            language=lang,
            size_bytes=size,
            line_count=lines,
            is_binary=is_binary,
        )
        files.append(info)
        total_size += size
        if lines is not None:
            total_lines += lines

        if lang is not None:
            cur = lang_acc.get(lang)
            if cur is None:
                lang_acc[lang] = LanguageStats(
                    name=lang,
                    file_count=1,
                    line_count=lines or 0,
                    bytes=size,
                )
            else:
                lang_acc[lang] = LanguageStats(
                    name=lang,
                    file_count=cur.file_count + 1,
                    line_count=cur.line_count + (lines or 0),
                    bytes=cur.bytes + size,
                )

    languages_sorted = sorted(lang_acc.values(), key=lambda x: (-x.line_count, x.name))
    entry_points, dep_graph = _detect_entry_points(root, files)
    file_paths_only = [f.path for f in files]
    conventions = conv_mod.extract(root, file_paths_only)
    call_graph = callgraph_mod.extract(root, file_paths_only)

    has_dep_data = bool(dep_graph.manifests or dep_graph.dependencies)
    return Architecture(
        # timezone-aware so the artifact's timestamp is unambiguous.
        generated_at=datetime.now(UTC),
        tool_version=__version__,
        repo=RepoMeta(
            name=root.name or str(root),
            root=str(root),
            total_files=len(files),
            total_size_bytes=total_size,
            total_lines=total_lines,
        ),
        languages=languages_sorted,
        entry_points=entry_points,
        files=files,
        dependencies=dep_graph if has_dep_data else None,
        conventions=conventions,
        call_graph=call_graph,
    )
