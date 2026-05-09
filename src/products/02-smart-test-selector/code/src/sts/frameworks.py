"""Test framework detection by file path.

We don't import any test framework here - we only need to recognize which
files are tests. Detection is conservative: paths matching multiple patterns
fall back to the more general framework. Unknown files return None (not
a test).
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from sts.models import TestFramework, TestKind, TestRef

# ---------------------------------------------------------------------------
# Manifest files - changing these means "we don't know what changed,
# run everything" by default in v0.0.1.
# ---------------------------------------------------------------------------

MANIFEST_FILES: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        "uv.lock",
        "poetry.lock",
        "Pipfile",
        "Pipfile.lock",
        "requirements.txt",
        "requirements-dev.txt",
        "Gemfile",
        "Gemfile.lock",
    }
)

# CI / build / config that, if changed, also shouldn't trust narrow selection.
CI_FILES: frozenset[str] = frozenset(
    {
        ".github/workflows",  # any file under here matches via prefix below
        "tox.ini",
        "pytest.ini",
        "noxfile.py",
        "Makefile",
        "Dockerfile",
        ".pre-commit-config.yaml",
    }
)


def is_high_impact_change(path: str) -> bool:
    """True if a change to this path means we can't trust narrow selection."""
    posix = path.replace("\\", "/")
    name = PurePosixPath(posix).name
    if name in MANIFEST_FILES:
        return True
    if name in CI_FILES:
        return True
    # Match files anywhere under .github/workflows/
    return posix.startswith(".github/workflows/") or "/.github/workflows/" in posix


# ---------------------------------------------------------------------------
# Test path patterns by framework
# ---------------------------------------------------------------------------


# pytest: tests/test_*.py, **/*_test.py, **/test_*.py
_PYTEST_RE = re.compile(r"(?:^|/)(?:tests?/.*\.py|.*_test\.py|test_[^/]+\.py)$")

# Jest / Vitest: **/*.test.{js,jsx,ts,tsx}, **/__tests__/**/*.{js,jsx,ts,tsx}, **/*.spec.{...}
_JS_TEST_RE = re.compile(
    r"(?:^|/)(?:.+\.(?:test|spec)\.(?:js|jsx|mjs|cjs|ts|tsx)|__tests__/.+\.(?:js|jsx|mjs|cjs|ts|tsx))$"
)

# Mocha: tests sit in a `test/` directory at the repo root by convention.
_MOCHA_RE = re.compile(r"^test/.+\.(?:js|mjs|cjs|ts)$")

# Go: file ends in _test.go anywhere
_GOTEST_RE = re.compile(r"(?:^|/).+_test\.go$")

# Cargo: tests/ at repo root, or any **/tests/*.rs.
_CARGO_RE = re.compile(r"(?:^|/)tests/[^/]+\.rs$")


def _classify_kind(posix_path: str) -> TestKind:
    """Best-effort kind classification from path hints.

    We're deliberately conservative: 'integration' / 'e2e' only when those
    words appear as path components.
    """
    parts = posix_path.lower().split("/")
    if any(p in {"e2e", "end-to-end", "endtoend"} for p in parts):
        return "e2e"
    if any(p in {"integration", "integration-tests", "integration_tests"} for p in parts):
        return "integration"
    if any(p in {"unit", "unit-tests", "unit_tests"} for p in parts):
        return "unit"
    return "unknown"


def detect(path: str) -> TestRef | None:
    """Detect whether a single path is a test, and which framework.

    Returns None if the path is not a recognized test file.
    Path may use Windows or POSIX separators; we normalize internally.
    """
    posix = path.replace("\\", "/")

    framework: TestFramework | None = None
    if _GOTEST_RE.search(posix):
        framework = "gotest"
    elif _CARGO_RE.search(posix):
        framework = "cargo"
    elif _JS_TEST_RE.search(posix):
        # Vitest and Jest share patterns; sts can't tell them apart by path
        # alone. We default to "jest" for v0.0.1; framework consumers that
        # care can re-classify by reading vitest.config.* themselves.
        framework = "jest"
    elif _MOCHA_RE.search(posix):
        framework = "mocha"
    elif _PYTEST_RE.search(posix):
        framework = "pytest"

    if framework is None:
        return None

    return TestRef(
        path=posix,
        framework=framework,
        kind=_classify_kind(posix),
    )


def detect_all(paths: list[str]) -> list[TestRef]:
    """Detect tests across a list of paths. Skips non-tests silently."""
    refs: list[TestRef] = []
    for p in paths:
        ref = detect(p)
        if ref is not None:
            refs.append(ref)
    return refs
