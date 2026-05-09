"""Manifest parsers - turn declared metadata into entry points and dependencies.

Replaces v0.0.x's filename-only heuristics. The four parsers here cover the
top language ecosystems for DevTrust's target users:

  - pyproject.toml  -> Python (PEP 621 + PEP 735 dependency-groups)
  - package.json    -> Node / TypeScript
  - Cargo.toml      -> Rust
  - go.mod          -> Go

Each parser is conservative: malformed files return empty results rather
than raising. Real-world repos contain partial / non-standard manifests
constantly.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Callable
from pathlib import Path

from repox.models import Dependency, DependencyKind, EntryPoint, ManifestInfo

# ---------------------------------------------------------------------------
# pyproject.toml (PEP 621)
# ---------------------------------------------------------------------------

_PEP508_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
_PEP508_SPEC_RE = re.compile(
    r"([><!=~^]+\s*[A-Za-z0-9._\-+*]+"
    r"(?:\s*,\s*[><!=~^]+\s*[A-Za-z0-9._\-+*]+)*)"
)


def _parse_pep508(raw: str, source: str, kind: DependencyKind) -> Dependency | None:
    """Light-touch PEP 508 parser. Pulls out name + version spec.

    Ignores extras and environment markers - we only need name + version
    for the architecture artifact, not full pip-resolver fidelity.
    """
    raw = raw.strip()
    if not raw:
        return None
    name_match = _PEP508_NAME_RE.match(raw)
    if not name_match:
        return None
    name = name_match.group(1)
    spec_match = _PEP508_SPEC_RE.search(raw[name_match.end() :])
    spec = spec_match.group(1).strip() if spec_match else None
    return Dependency(name=name, version_spec=spec, source=source, kind=kind)


def parse_pyproject(
    path: Path,
) -> tuple[list[EntryPoint], list[Dependency], ManifestInfo | None]:
    """Parse a pyproject.toml. Returns (entry_points, dependencies, info)."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return [], [], None

    project = data.get("project", {})
    if not isinstance(project, dict):
        info = ManifestInfo(path=str(path), kind="pyproject", dependency_count=0)
        return [], [], info

    eps: list[EntryPoint] = []
    deps: list[Dependency] = []

    scripts = project.get("scripts", {})
    if isinstance(scripts, dict):
        for script_name, target in scripts.items():
            if isinstance(target, str):
                eps.append(
                    EntryPoint(
                        path=str(path.name),
                        kind="pyproject:scripts",
                        detail=f"{script_name} -> {target}",
                    )
                )

    gui = project.get("gui-scripts", {})
    if isinstance(gui, dict):
        for script_name, target in gui.items():
            if isinstance(target, str):
                eps.append(
                    EntryPoint(
                        path=str(path.name),
                        kind="pyproject:gui-scripts",
                        detail=f"{script_name} -> {target}",
                    )
                )

    runtime = project.get("dependencies", [])
    if isinstance(runtime, list):
        for raw in runtime:
            if isinstance(raw, str):
                d = _parse_pep508(raw, "pyproject.toml", "runtime")
                if d is not None:
                    deps.append(d)

    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for group_deps in optional.values():
            if isinstance(group_deps, list):
                for raw in group_deps:
                    if isinstance(raw, str):
                        d = _parse_pep508(raw, "pyproject.toml", "optional")
                        if d is not None:
                            deps.append(d)

    dep_groups = data.get("dependency-groups", {})
    if isinstance(dep_groups, dict):
        for group_name, group_deps in dep_groups.items():
            group_kind: DependencyKind = (
                "dev" if group_name.lower() in {"dev", "test", "lint", "type"} else "optional"
            )
            if isinstance(group_deps, list):
                for raw in group_deps:
                    if isinstance(raw, str):
                        d = _parse_pep508(raw, "pyproject.toml", group_kind)
                        if d is not None:
                            deps.append(d)

    info = ManifestInfo(
        path=str(path),
        kind="pyproject",
        package_name=project.get("name") if isinstance(project.get("name"), str) else None,
        package_version=(
            project.get("version") if isinstance(project.get("version"), str) else None
        ),
        dependency_count=len(deps),
    )
    return eps, deps, info


# ---------------------------------------------------------------------------
# package.json
# ---------------------------------------------------------------------------


def parse_package_json(
    path: Path,
) -> tuple[list[EntryPoint], list[Dependency], ManifestInfo | None]:
    """Parse a package.json. Returns (entry_points, dependencies, info)."""
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [], [], None

    if not isinstance(data, dict):
        return [], [], None

    eps: list[EntryPoint] = []
    deps: list[Dependency] = []
    name = data.get("name")

    if isinstance(data.get("main"), str):
        eps.append(
            EntryPoint(
                path=data["main"],
                kind="package.json:main",
                detail=f"declared main of {name or 'package'}",
            )
        )

    bins = data.get("bin")
    if isinstance(bins, dict):
        for bin_name, p in bins.items():
            if isinstance(p, str):
                eps.append(EntryPoint(path=p, kind="package.json:bin", detail=str(bin_name)))
    elif isinstance(bins, str):
        eps.append(EntryPoint(path=bins, kind="package.json:bin"))

    exports = data.get("exports")
    if isinstance(exports, dict):
        root_export = exports.get(".")
        if isinstance(root_export, str):
            eps.append(EntryPoint(path=root_export, kind="package.json:exports"))
        elif isinstance(root_export, dict):
            for key in ("default", "import", "require", "node"):
                if isinstance(root_export.get(key), str):
                    eps.append(
                        EntryPoint(
                            path=root_export[key],
                            kind="package.json:exports",
                            detail=f"exports['.'][{key!r}]",
                        )
                    )
                    break

    npm_groups: list[tuple[DependencyKind, str]] = [
        ("runtime", "dependencies"),
        ("dev", "devDependencies"),
        ("optional", "optionalDependencies"),
        ("optional", "peerDependencies"),
    ]
    for kind, key in npm_groups:
        section = data.get(key, {})
        if isinstance(section, dict):
            for dep_name, ver in section.items():
                if isinstance(dep_name, str):
                    deps.append(
                        Dependency(
                            name=dep_name,
                            version_spec=str(ver) if ver is not None else None,
                            source="package.json",
                            kind=kind,
                        )
                    )

    info = ManifestInfo(
        path=str(path),
        kind="package.json",
        package_name=name if isinstance(name, str) else None,
        package_version=data.get("version") if isinstance(data.get("version"), str) else None,
        dependency_count=len(deps),
    )
    return eps, deps, info


# ---------------------------------------------------------------------------
# Cargo.toml
# ---------------------------------------------------------------------------


def parse_cargo_toml(
    path: Path,
) -> tuple[list[EntryPoint], list[Dependency], ManifestInfo | None]:
    """Parse a Cargo.toml. Returns (entry_points, dependencies, info)."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return [], [], None

    eps: list[EntryPoint] = []
    deps: list[Dependency] = []

    pkg = data.get("package", {}) if isinstance(data.get("package"), dict) else {}
    name = pkg.get("name") if isinstance(pkg.get("name"), str) else None
    version = pkg.get("version") if isinstance(pkg.get("version"), str) else None

    bins = data.get("bin", [])
    if isinstance(bins, list):
        for b in bins:
            if isinstance(b, dict):
                bin_name = b.get("name")
                bin_path = b.get("path", "src/main.rs")
                if isinstance(bin_path, str):
                    eps.append(
                        EntryPoint(
                            path=bin_path,
                            kind="Cargo.toml:bin",
                            detail=str(bin_name) if bin_name else None,
                        )
                    )

    lib = data.get("lib")
    if isinstance(lib, dict):
        lib_path = lib.get("path", "src/lib.rs")
        if isinstance(lib_path, str):
            eps.append(EntryPoint(path=lib_path, kind="Cargo.toml:lib"))

    cargo_groups: list[tuple[DependencyKind, str]] = [
        ("runtime", "dependencies"),
        ("dev", "dev-dependencies"),
        ("build", "build-dependencies"),
    ]
    for kind, key in cargo_groups:
        section = data.get(key, {})
        if isinstance(section, dict):
            for dep_name, val in section.items():
                if isinstance(dep_name, str):
                    spec: str | None
                    if isinstance(val, str):
                        spec = val
                    elif isinstance(val, dict):
                        v = val.get("version")
                        spec = v if isinstance(v, str) else None
                    else:
                        spec = None
                    deps.append(
                        Dependency(
                            name=dep_name,
                            version_spec=spec,
                            source="Cargo.toml",
                            kind=kind,
                        )
                    )

    info = ManifestInfo(
        path=str(path),
        kind="Cargo.toml",
        package_name=name,
        package_version=version,
        dependency_count=len(deps),
    )
    return eps, deps, info


# ---------------------------------------------------------------------------
# go.mod
# ---------------------------------------------------------------------------

_GO_MODULE_RE = re.compile(r"^module\s+(\S+)", re.MULTILINE)
_GO_REQUIRE_LINE_RE = re.compile(r"^\s*([\w./-]+)\s+(\S+)")
_GO_REQUIRE_BLOCK_RE = re.compile(r"require\s*\(([^)]*)\)", re.DOTALL)
_GO_REQUIRE_SINGLE_RE = re.compile(r"^require\s+([\w./-]+)\s+(\S+)\s*$", re.MULTILINE)


def parse_go_mod(
    path: Path,
) -> tuple[list[EntryPoint], list[Dependency], ManifestInfo | None]:
    """Parse a go.mod. Returns (entry_points, dependencies, info)."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], [], None

    eps: list[EntryPoint] = []
    deps: list[Dependency] = []

    name_match = _GO_MODULE_RE.search(text)
    name = name_match.group(1) if name_match else None

    eps.append(
        EntryPoint(
            path="go.mod",
            kind="go:module",
            detail=f"module {name}" if name else "Go module declaration",
        )
    )

    for block in _GO_REQUIRE_BLOCK_RE.findall(text):
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            m = _GO_REQUIRE_LINE_RE.match(stripped)
            if m:
                deps.append(
                    Dependency(
                        name=m.group(1),
                        version_spec=m.group(2),
                        source="go.mod",
                        kind="runtime",
                    )
                )

    for m in _GO_REQUIRE_SINGLE_RE.finditer(text):
        deps.append(
            Dependency(
                name=m.group(1),
                version_spec=m.group(2),
                source="go.mod",
                kind="runtime",
            )
        )

    info = ManifestInfo(
        path=str(path),
        kind="go.mod",
        package_name=name,
        package_version=None,
        dependency_count=len(deps),
    )
    return eps, deps, info


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

ParserFn = Callable[[Path], tuple[list[EntryPoint], list[Dependency], "ManifestInfo | None"]]

PARSERS: list[tuple[str, ParserFn]] = [
    ("pyproject.toml", parse_pyproject),
    ("package.json", parse_package_json),
    ("Cargo.toml", parse_cargo_toml),
    ("go.mod", parse_go_mod),
]


def parse_all(
    root: Path,
) -> tuple[list[EntryPoint], list[Dependency], list[ManifestInfo]]:
    """Find and parse all known manifests at the repo root.

    For v0.1 this is top-level only; nested packages (monorepos, workspaces)
    will be handled in v0.2 alongside call-graph extraction.
    """
    all_eps: list[EntryPoint] = []
    all_deps: list[Dependency] = []
    infos: list[ManifestInfo] = []

    for filename, parser in PARSERS:
        path = root / filename
        if path.is_file():
            eps, deps, info = parser(path)
            all_eps.extend(eps)
            all_deps.extend(deps)
            if info is not None:
                infos.append(info)

    return all_eps, all_deps, infos
