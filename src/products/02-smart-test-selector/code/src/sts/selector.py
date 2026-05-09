"""The affecting engine - given a repo's architecture and a set of changed
files, produce a SelectionReport classifying every test as must / should / skip.

v0.0.3 heuristics (in order):

  1. If any changed path is a "high-impact" file (manifest, lockfile, CI
     config, Dockerfile), short-circuit to "run everything" with
     `fallback_run_all=True` and a clear reason.

  2. Otherwise, for each test we walk five rules. A test that hits any
     of them becomes must-run (we record every reason that fired):

     a. Test file directly modified.
     b. Sibling test in the same directory as a changed source file.
     c. Naming-convention match (test_<name>.py for <name>.py,
        <name>.test.ts for <name>.ts, etc.).
     d. Mirror-tree match (`src/<pkg>/foo.py` <-> `tests/<pkg>/test_foo.py`).
     e. Package-boundary match -- tests inside the same enclosing
        manifest (pyproject / package.json / Cargo / go.mod) as a
        changed source.
     f. **Transitive-import match (NEW in v0.0.3)** -- requires a repox
        artifact with a CallGraph. We build the reverse-import graph
        from the artifact's imports list, then walk outward from every
        changed source. Any test that transitively imports the changed
        file becomes must-run, with a `transitive import (depth N)`
        reason.

  3. Tests not classified as must-run remain should-run by default
     (we never silently skip on uncertainty in v0.0.3).
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from sts import __version__
from sts.frameworks import detect_all, is_high_impact_change
from sts.models import (
    RepoxArtifact,
    SelectionInputs,
    SelectionReport,
    SelectionStats,
    TestRef,
    TestSelection,
)

_PACKAGE_MANIFESTS: frozenset[str] = frozenset(
    {"pyproject.toml", "package.json", "Cargo.toml", "go.mod"}
)

# Cap on the BFS depth for transitive-import affecting. Effectively
# unlimited for normal monorepos; the limit is a safety net against
# pathological cycles or extremely deep import chains.
_MAX_TRANSITIVE_DEPTH = 20


def _conventional_match(changed_posix: str, test_posix: str) -> bool:
    """True if `test_posix` looks like the conventional test for `changed_posix`."""
    if changed_posix == test_posix:
        return True
    changed_p = PurePosixPath(changed_posix)
    test_p = PurePosixPath(test_posix)
    base = changed_p.stem
    if not base:
        return False

    test_name = test_p.name
    pytest_pairs = (f"test_{base}.py", f"{base}_test.py")
    js_pairs = tuple(
        f"{base}.{kind}.{ext}"
        for kind in ("test", "spec")
        for ext in ("js", "jsx", "mjs", "cjs", "ts", "tsx")
    )
    go_pair = (f"{base}_test.go",)
    rust_pair = (f"{base}.rs",)

    return test_name in pytest_pairs + js_pairs + go_pair + rust_pair


def _same_dir(a_posix: str, b_posix: str) -> bool:
    return str(PurePosixPath(a_posix).parent) == str(PurePosixPath(b_posix).parent)


def _mirror_tree_match(changed_posix: str, test_posix: str) -> bool:
    if "/" not in changed_posix or "/" not in test_posix:
        return False
    cparts = changed_posix.split("/")
    tparts = test_posix.split("/")
    for marker_src, marker_tests in (
        ("src", "tests"),
        ("src", "test"),
        ("lib", "tests"),
    ):
        if marker_src in cparts and marker_tests in tparts:
            ci = cparts.index(marker_src)
            ti = tparts.index(marker_tests)
            csub = cparts[ci + 1 : -1]
            tsub = tparts[ti + 1 : -1]
            if csub == tsub:
                return _conventional_match(cparts[-1], tparts[-1])
    return False


def _find_package_roots(repo_files: list[str]) -> list[str]:
    """Return sorted list of directories that contain a package manifest."""
    roots: set[str] = set()
    for f in repo_files:
        name = PurePosixPath(f).name
        if name in _PACKAGE_MANIFESTS:
            parent = str(PurePosixPath(f).parent)
            roots.add("" if parent == "." else parent)
    return sorted(roots)


def _enclosing_package(path: str, package_roots: list[str]) -> str | None:
    """Return the longest package root that contains this path."""
    best: str | None = None
    for root in package_roots:
        if not root:
            if best is None:
                best = ""
            continue
        prefix = root + "/"
        if path.startswith(prefix) and (best is None or len(root) > len(best)):
            best = root
    return best


def _build_reverse_imports(
    imports_by_source: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Given source -> [targets], return target -> [sources that import it]."""
    rev: dict[str, list[str]] = {}
    for src, targets in imports_by_source.items():
        for tgt in targets:
            rev.setdefault(tgt, []).append(src)
    return {k: sorted(set(v)) for k, v in rev.items()}


def _transitive_importers(
    starts: list[str],
    reverse_imports: dict[str, list[str]],
    max_depth: int = _MAX_TRANSITIVE_DEPTH,
) -> dict[str, int]:
    """BFS outward from `starts`. Return file -> shallowest depth reached.

    Depth 0 is the starting file itself. Depth 1 is direct importers.
    Cycles are handled - a file already visited at a shallower depth
    keeps its earlier depth.
    """
    depths: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque((s, 0) for s in starts)
    while queue:
        node, d = queue.popleft()
        if node in depths:
            continue
        depths[node] = d
        if d >= max_depth:
            continue
        for parent in reverse_imports.get(node, []):
            if parent not in depths:
                queue.append((parent, d + 1))
    return depths


def select(
    repo_root: Path,
    repo_files: list[str],
    changed_files: list[str],
    diff_source: str = "cli",
    repox_artifact: RepoxArtifact | None = None,
) -> SelectionReport:
    """Run the v0.0.3 heuristics and return a full SelectionReport."""
    all_tests: list[TestRef] = detect_all(repo_files)
    test_paths: set[str] = {t.path for t in all_tests}

    # Step 1: high-impact short-circuit?
    high_impact = [c for c in changed_files if is_high_impact_change(c)]
    if high_impact:
        reason = (
            "high-impact file(s) changed: "
            + ", ".join(sorted(high_impact)[:5])
            + (" ..." if len(high_impact) > 5 else "")
        )
        all_must_selections = [
            TestSelection(test=t, priority="must", reason=reason) for t in all_tests
        ]
        stats = SelectionStats(
            total_tests_in_repo=len(all_tests),
            must_run=len(all_tests),
            should_run=0,
            can_skip=0,
        )
        return SelectionReport(
            generated_at=datetime.now(UTC),
            tool_version=__version__,
            inputs=SelectionInputs(
                repo_root=str(repo_root),
                changed_files=sorted(changed_files),
                diff_source=_safe_diff_source(diff_source),
                used_repox_artifact=repox_artifact is not None,
            ),
            stats=stats,
            selections=all_must_selections,
            fallback_run_all=True,
            fallback_reason=reason,
        )

    # Step 2: package boundary discovery
    package_roots = _find_package_roots(repo_files)

    tests_by_package: dict[str, list[str]] = {}
    for tp in test_paths:
        pkg = _enclosing_package(tp, package_roots)
        if pkg is not None:
            tests_by_package.setdefault(pkg, []).append(tp)

    # Step 3: transitive-import affecting (NEW in v0.0.3)
    reverse_imports: dict[str, list[str]] = {}
    transitive_depths: dict[str, int] = {}
    if repox_artifact is not None and repox_artifact.imports_by_source:
        reverse_imports = _build_reverse_imports(repox_artifact.imports_by_source)
        # BFS from every changed file that's actually a known node in the
        # graph. Files not in the graph still get the per-test heuristics.
        seeds = [
            c
            for c in changed_files
            if c in reverse_imports or c in repox_artifact.imports_by_source
        ]
        if not seeds:
            # Even unknown files might transitively reach known code via
            # the reverse map - try seeding directly.
            seeds = list(changed_files)
        transitive_depths = _transitive_importers(seeds, reverse_imports)

    # Step 4: per-test affecting
    must_reasons: dict[str, list[str]] = {p: [] for p in test_paths}

    for cf in changed_files:
        if cf in test_paths:
            must_reasons[cf].append("test file directly modified")
            continue
        for tp in test_paths:
            if _same_dir(cf, tp):
                must_reasons[tp].append(f"sibling test in same directory as {cf}")
            elif _conventional_match(cf, tp):
                must_reasons[tp].append(f"naming-convention match for {cf}")
            elif _mirror_tree_match(cf, tp):
                must_reasons[tp].append(f"mirror-tree match for {cf}")

        cf_package = _enclosing_package(cf, package_roots)
        if cf_package is not None:
            pkg_label = cf_package or "<repo root>"
            for tp in tests_by_package.get(cf_package, []):
                must_reasons[tp].append(f"same package ({pkg_label}) as {cf}")

    # Apply the transitive-import heuristic last, so its `reason` strings
    # appear after the directly-pairwise ones (cleaner UX).
    for tp in test_paths:
        depth = transitive_depths.get(tp)
        if depth is not None and depth > 0:
            must_reasons[tp].append(f"transitive import (depth {depth}) of changed file")

    selections: list[TestSelection] = []
    must_run = 0
    should_run = 0
    for t in all_tests:
        reasons = must_reasons.get(t.path, [])
        if reasons:
            shown = reasons[:3]
            extra = f" (+{len(reasons) - 3} more)" if len(reasons) > 3 else ""
            selections.append(
                TestSelection(
                    test=t,
                    priority="must",
                    reason="; ".join(shown) + extra,
                )
            )
            must_run += 1
        else:
            selections.append(
                TestSelection(
                    test=t,
                    priority="should",
                    reason="no direct affecting evidence; safe-default include",
                )
            )
            should_run += 1

    stats = SelectionStats(
        total_tests_in_repo=len(all_tests),
        must_run=must_run,
        should_run=should_run,
        can_skip=0,
    )
    return SelectionReport(
        generated_at=datetime.now(UTC),
        tool_version=__version__,
        inputs=SelectionInputs(
            repo_root=str(repo_root),
            changed_files=sorted(changed_files),
            diff_source=_safe_diff_source(diff_source),
            used_repox_artifact=repox_artifact is not None,
        ),
        stats=stats,
        selections=selections,
        fallback_run_all=False,
        fallback_reason=None,
    )


def _safe_diff_source(
    label: str,
) -> Literal["cli", "diff-file", "git-auto", "stdin"]:
    """Coerce free-form input to one of the SelectionInputs.diff_source literals."""
    if label == "diff-file":
        return "diff-file"
    if label == "git-auto":
        return "git-auto"
    if label == "stdin":
        return "stdin"
    return "cli"
