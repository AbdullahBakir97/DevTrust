#!/usr/bin/env python3
"""Pre-flight release checks for the DevTrust monorepo.

Usage:
    python scripts/release.py --check                # gate run only
    python scripts/release.py --package repox        # check one package
    python scripts/release.py --tag-suggestion repox # print the tag string we'll push

What this does (and only this):

    1. Reads each per-product `pyproject.toml` to extract `version`.
    2. Confirms `__version__` in `src/{name}/__init__.py` matches.
    3. Confirms the package's `CHANGELOG.md` has a `## [{version}]` entry.
    4. Runs `ruff check`, `ruff format --check`, `mypy`, and per-package
       `pytest --no-cov` and reports pass/fail per gate.

It does NOT push tags, build wheels, or upload to PyPI. Those are the
release.yml workflow's job once a tag lands.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_ROOT = REPO_ROOT / "src" / "products"


@dataclass(frozen=True)
class Package:
    """One workspace member."""

    name: str  # importable / distribution name (e.g. "repox", "sts-app")
    pyproject: Path
    init_py: Path
    changelog: Path
    tests: Path

    @property
    def display(self) -> str:
        return f"{self.name} ({self.pyproject.parent.relative_to(REPO_ROOT)})"


def discover_packages() -> list[Package]:
    """Find every uv-workspace member under `src/products/*/{code,app}/`."""
    out: list[Package] = []
    for product_dir in sorted(PRODUCTS_ROOT.iterdir()):
        if not product_dir.is_dir():
            continue
        for sub in ("code", "app"):
            pkg_root = product_dir / sub
            pyproj = pkg_root / "pyproject.toml"
            if not pyproj.is_file():
                continue
            data = tomllib.loads(pyproj.read_text(encoding="utf-8"))
            project = data.get("project", {})
            dist_name = project.get("name")
            if not isinstance(dist_name, str):
                continue
            # Convention: distribution name == importable package name
            # except dashes -> underscores.
            module_name = dist_name.replace("-", "_")
            init_py = pkg_root / "src" / module_name / "__init__.py"
            out.append(
                Package(
                    name=dist_name,
                    pyproject=pyproj,
                    init_py=init_py,
                    changelog=pkg_root / "CHANGELOG.md",
                    tests=pkg_root / "tests",
                )
            )
    return out


def read_pyproject_version(pyproj: Path) -> str | None:
    data = tomllib.loads(pyproj.read_text(encoding="utf-8"))
    project = data.get("project", {})
    v = project.get("version")
    return v if isinstance(v, str) else None


_INIT_VERSION_RE = re.compile(r'__version__\s*=\s*["\']([0-9][^"\']*)["\']', re.MULTILINE)


def read_init_version(init_py: Path) -> str | None:
    if not init_py.is_file():
        return None
    text = init_py.read_text(encoding="utf-8")
    m = _INIT_VERSION_RE.search(text)
    return m.group(1) if m else None


def check_changelog_has_version(changelog: Path, version: str) -> bool:
    if not changelog.is_file():
        return False
    needle = f"## [{version}]"
    return needle in changelog.read_text(encoding="utf-8")


def run(cmd: list[str], cwd: Path = REPO_ROOT) -> tuple[int, str]:
    """Run a shell command. Capture combined stdout+stderr."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def gate_ruff_check() -> tuple[bool, str]:
    code, out = run(["uv", "run", "ruff", "check", "."])
    return code == 0, out.strip()


def gate_ruff_format() -> tuple[bool, str]:
    code, out = run(["uv", "run", "ruff", "format", "--check", "."])
    return code == 0, out.strip()


def gate_mypy() -> tuple[bool, str]:
    code, out = run(["uv", "run", "mypy"])
    return code == 0, out.strip()


def gate_pytest(pkg: Package) -> tuple[bool, str]:
    if not pkg.tests.is_dir():
        return True, "(no tests dir)"
    rel = pkg.tests.relative_to(REPO_ROOT)
    code, out = run(["uv", "run", "pytest", str(rel), "--no-cov", "-q"])
    return code == 0, out.strip().splitlines()[-1] if out.strip() else ""


_STALE_PIN_RE = re.compile(r'assert\s+__version__\s*==\s*["\']([0-9]+\.[0-9]+\.[0-9]+)["\']')


def _check_no_stale_version_pins(pkg: Package, current_version: str) -> list[str]:
    """Walk the package's tests for `assert __version__ == "X.Y.Z"` lines that
    reference a version other than the current one. Hardcoded equality
    against an old version is the dominant cause of "works locally,
    breaks at release" failures we've already hit three times.

    Use a structural SemVer regex check (matches `MAJOR.MINOR.PATCH`)
    inside tests instead -- it survives bumps without edits.
    """
    if not pkg.tests.is_dir():
        return []
    bad: list[str] = []
    for test_file in pkg.tests.rglob("*.py"):
        try:
            content = test_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _STALE_PIN_RE.finditer(content):
            pinned = match.group(1)
            if pinned != current_version:
                rel: str
                try:
                    rel = str(test_file.relative_to(REPO_ROOT))
                except ValueError:
                    rel = str(test_file)
                bad.append(
                    f"{pkg.display}: {rel} pins __version__=={pinned!r} "
                    f"but current is {current_version!r}; replace with a "
                    "structural SemVer regex check."
                )
    return bad


def check_package(pkg: Package) -> list[str]:
    """Return a list of error strings; empty means OK."""
    errors: list[str] = []

    pyproj_v = read_pyproject_version(pkg.pyproject)
    init_v = read_init_version(pkg.init_py)

    if pyproj_v is None:
        errors.append(f"{pkg.display}: pyproject.toml has no [project].version")
        return errors
    if init_v is None:
        errors.append(f"{pkg.display}: {pkg.init_py.relative_to(REPO_ROOT)} missing __version__")
    elif pyproj_v != init_v:
        errors.append(
            f"{pkg.display}: pyproject version {pyproj_v!r} != __init__ version {init_v!r}"
        )

    if not check_changelog_has_version(pkg.changelog, pyproj_v):
        errors.append(f"{pkg.display}: CHANGELOG.md missing `## [{pyproj_v}]` section")

    errors.extend(_check_no_stale_version_pins(pkg, pyproj_v))

    return errors


def cmd_check(args: argparse.Namespace) -> int:
    packages = discover_packages()
    if args.package:
        packages = [p for p in packages if p.name == args.package]
        if not packages:
            print(f"unknown package: {args.package!r}")
            return 2

    print("== Per-package metadata check ==")
    metadata_failures = 0
    for pkg in packages:
        errs = check_package(pkg)
        if errs:
            metadata_failures += 1
            for e in errs:
                print(f"  FAIL  {e}")
        else:
            v = read_pyproject_version(pkg.pyproject)
            print(f"  ok    {pkg.display} @ {v}")

    print()
    print("== Workspace gates ==")
    results: list[tuple[str, bool, str]] = []
    for label, fn in (
        ("ruff check", gate_ruff_check),
        ("ruff format --check", gate_ruff_format),
        ("mypy --strict", gate_mypy),
    ):
        ok, msg = fn()
        results.append((label, ok, msg))
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
        if not ok:
            for line in msg.splitlines()[-12:]:
                print(f"        {line}")

    print()
    print("== Per-package tests ==")
    for pkg in packages:
        ok, summary = gate_pytest(pkg)
        results.append((f"pytest:{pkg.name}", ok, summary))
        print(f"  {'ok  ' if ok else 'FAIL'}  {pkg.display}  {summary}")

    failures = metadata_failures + sum(1 for _, ok, _ in results if not ok)
    print()
    if failures == 0:
        print("READY TO RELEASE")
        return 0
    print(f"BLOCKED -- {failures} failure(s); fix before tagging")
    return 1


def cmd_tag(args: argparse.Namespace) -> int:
    """Print the suggested git tag string for a given package."""
    packages = discover_packages()
    pkg = next((p for p in packages if p.name == args.package), None)
    if pkg is None:
        print(f"unknown package: {args.package!r}")
        return 2
    v = read_pyproject_version(pkg.pyproject)
    print(f"{pkg.name}-v{v}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DevTrust release pre-flight",
    )
    parser.add_argument("--check", action="store_true", help="run all gates (default)")
    parser.add_argument(
        "--package",
        type=str,
        default=None,
        help="restrict to one package (e.g. repox, sts, sts-app, apr, apr-app)",
    )
    parser.add_argument(
        "--tag-suggestion",
        dest="tag_package",
        type=str,
        default=None,
        help="print the tag string for one package and exit",
    )
    args = parser.parse_args()

    if args.tag_package:
        ns = argparse.Namespace(package=args.tag_package)
        return cmd_tag(ns)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
