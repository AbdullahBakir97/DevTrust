"""Smoke + unit tests for sts v0.0.1.

Coverage:
  - frameworks:  pytest / jest / gotest / cargo detection, kind classification
  - frameworks:  high-impact change detection
  - diff:        unified-diff parsing, plain-list parsing, normalization
  - selector:    manifest-edge fallback, sibling tests, mirror-tree, convention
  - cli:         version, info, select (against the synthetic repo)

Run end-to-end against the synthetic repo built by conftest.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from sts import __version__
from sts.cli import _list_repo_files, app
from sts.diff import (
    from_cli_args,
    from_path_list_file,
    from_unified_diff,
)
from sts.frameworks import (
    detect,
    is_high_impact_change,
)
from sts.selector import select as select_engine
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# frameworks
# ---------------------------------------------------------------------------


def test_detect_pytest() -> None:
    ref = detect("tests/test_foo.py")
    assert ref is not None
    assert ref.framework == "pytest"


def test_detect_jest_test_dot_ts() -> None:
    ref = detect("__tests__/utils.test.ts")
    assert ref is not None
    assert ref.framework == "jest"


def test_detect_gotest() -> None:
    ref = detect("cmd/main_test.go")
    assert ref is not None
    assert ref.framework == "gotest"


def test_detect_cargo() -> None:
    ref = detect("crate/tests/smoke.rs")
    assert ref is not None
    assert ref.framework == "cargo"


def test_detect_returns_none_for_nontest() -> None:
    assert detect("src/app/foo.py") is None
    assert detect("README.md") is None


def test_kind_e2e_when_path_contains_e2e() -> None:
    ref = detect("tests/e2e/test_login.py")
    assert ref is not None
    assert ref.kind == "e2e"


def test_high_impact_manifests() -> None:
    assert is_high_impact_change("pyproject.toml")
    assert is_high_impact_change("package.json")
    assert is_high_impact_change("yarn.lock")
    assert is_high_impact_change(".github/workflows/ci.yml")
    assert not is_high_impact_change("src/app/foo.py")


# ---------------------------------------------------------------------------
# diff parsing
# ---------------------------------------------------------------------------


def test_diff_from_cli_args_normalizes_separators(tmp_path: Path) -> None:
    out = from_cli_args([r"src\app\foo.py", "tests/test_foo.py"], tmp_path)
    assert out == ["src/app/foo.py", "tests/test_foo.py"]


def test_diff_from_unified_diff_extracts_paths(tmp_path: Path) -> None:
    raw = (
        "diff --git a/src/app/foo.py b/src/app/foo.py\n"
        "index 0000001..0000002 100644\n"
        "--- a/src/app/foo.py\n"
        "+++ b/src/app/foo.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    out = from_unified_diff(raw, tmp_path)
    assert "src/app/foo.py" in out


def test_diff_from_path_list_file_skips_blanks_and_comments(tmp_path: Path) -> None:
    raw = "src/app/foo.py\n# a comment\n\nsrc/app/bar.py\n"
    out = from_path_list_file(raw, tmp_path)
    assert out == ["src/app/foo.py", "src/app/bar.py"]


# ---------------------------------------------------------------------------
# selector engine
# ---------------------------------------------------------------------------


def test_selector_manifest_change_runs_all(sample_repo: Path) -> None:
    repo_files = _list_repo_files(sample_repo)
    report = select_engine(sample_repo, repo_files, ["pyproject.toml"])
    assert report.fallback_run_all is True
    assert report.fallback_reason is not None
    assert all(s.priority == "must" for s in report.selections)
    assert report.stats.must_run == report.stats.total_tests_in_repo


def test_selector_naming_convention_match(sample_repo: Path) -> None:
    repo_files = _list_repo_files(sample_repo)
    report = select_engine(sample_repo, repo_files, ["src/app/foo.py"])
    paths_must = {s.test.path for s in report.selections if s.priority == "must"}
    # tests/test_foo.py is a naming-convention match for src/app/foo.py
    assert "tests/test_foo.py" in paths_must


def test_selector_mirror_tree_match(sample_repo: Path) -> None:
    repo_files = _list_repo_files(sample_repo)
    report = select_engine(sample_repo, repo_files, ["src/app/bar.py"])
    paths_must = {s.test.path for s in report.selections if s.priority == "must"}
    # tests/app/test_bar.py mirrors src/app/bar.py
    assert "tests/app/test_bar.py" in paths_must


def test_selector_sibling_test(sample_repo: Path) -> None:
    repo_files = _list_repo_files(sample_repo)
    report = select_engine(sample_repo, repo_files, ["cmd/main.go"])
    paths_must = {s.test.path for s in report.selections if s.priority == "must"}
    # main_test.go sits in the same directory as main.go
    assert "cmd/main_test.go" in paths_must


def test_selector_unaffected_test_is_should_run(sample_repo: Path) -> None:
    repo_files = _list_repo_files(sample_repo)
    report = select_engine(sample_repo, repo_files, ["src/app/foo.py"])
    # cmd/main_test.go has no relation to src/app/foo.py - safe-default should
    by_path = {s.test.path: s.priority for s in report.selections}
    assert by_path["cmd/main_test.go"] == "should"


def test_selector_no_changes_means_all_should_run(sample_repo: Path) -> None:
    repo_files = _list_repo_files(sample_repo)
    report = select_engine(sample_repo, repo_files, [])
    assert report.fallback_run_all is False
    assert all(s.priority == "should" for s in report.selections)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_version_prints_version() -> None:
    import re

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    # Rich emits ANSI escape codes when CI sets FORCE_COLOR=1; strip them
    # so the substring check works regardless of terminal styling.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert __version__ in plain


def test_cli_info_does_not_write_files(sample_repo: Path) -> None:
    result = runner.invoke(app, ["info", "--repo", str(sample_repo)])
    assert result.exit_code == 0
    assert not (sample_repo / ".sts").exists()


def test_cli_select_writes_artifacts(sample_repo: Path) -> None:
    result = runner.invoke(
        app, ["select", "--repo", str(sample_repo), "--changed", "src/app/foo.py"]
    )
    assert result.exit_code == 0
    json_path = sample_repo / ".sts" / "selection.json"
    md_path = sample_repo / ".sts" / "selection.md"
    assert json_path.is_file()
    assert md_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.2.0"
    assert data["tool_version"] == __version__
    assert data["fallback_run_all"] is False


def test_cli_select_quiet_is_quiet(sample_repo: Path) -> None:
    result = runner.invoke(
        app,
        [
            "select",
            "--repo",
            str(sample_repo),
            "--changed",
            "src/app/foo.py",
            "--quiet",
        ],
    )
    assert result.exit_code == 0
    assert "Selecting tests for" not in result.stdout


# ---------------------------------------------------------------------------
# v0.0.2: repox integration + package-boundary heuristic
# ---------------------------------------------------------------------------


def test_repox_integration_loads_artifact(tmp_path: Path) -> None:
    """If `.repox/architecture.json` exists, repox_integration.load_files
    parses it and returns the file list."""
    from sts.repox_integration import load_files

    repox_dir = tmp_path / ".repox"
    repox_dir.mkdir()
    arch = {
        "schema_version": "0.1.0",
        "tool_version": "0.1.0",
        "files": [
            {"path": "src/foo.py", "language": "Python", "size_bytes": 1, "is_binary": False},
            {
                "path": "tests/test_foo.py",
                "language": "Python",
                "size_bytes": 1,
                "is_binary": False,
            },
        ],
    }
    (repox_dir / "architecture.json").write_text(json.dumps(arch), encoding="utf-8")

    artifact = load_files(tmp_path)
    assert artifact is not None
    assert "src/foo.py" in artifact.paths
    assert "tests/test_foo.py" in artifact.paths
    assert artifact.tool_version == "0.1.0"
    assert artifact.incompatible_schema is False


def test_repox_integration_returns_none_when_missing(tmp_path: Path) -> None:
    from sts.repox_integration import load_files

    assert load_files(tmp_path) is None


def test_repox_integration_returns_none_for_invalid_json(tmp_path: Path) -> None:
    from sts.repox_integration import load_files

    repox_dir = tmp_path / ".repox"
    repox_dir.mkdir()
    (repox_dir / "architecture.json").write_text("{not json", encoding="utf-8")
    assert load_files(tmp_path) is None


def test_package_boundary_scopes_tests_to_their_package(tmp_path: Path) -> None:
    """A monorepo with two packages: a change in package A must not pull
    package B's tests as must-run."""
    from sts.cli import _list_repo_files
    from sts.selector import select as select_engine

    root = tmp_path / "monorepo"
    root.mkdir()

    # Package A
    pkg_a = root / "packages" / "a"
    pkg_a.mkdir(parents=True)
    (pkg_a / "pyproject.toml").write_text('[project]\nname = "a"\n', encoding="utf-8")
    (pkg_a / "src").mkdir()
    (pkg_a / "src" / "core.py").write_text("def x(): return 1\n", encoding="utf-8")
    (pkg_a / "tests").mkdir()
    (pkg_a / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")

    # Package B
    pkg_b = root / "packages" / "b"
    pkg_b.mkdir(parents=True)
    (pkg_b / "pyproject.toml").write_text('[project]\nname = "b"\n', encoding="utf-8")
    (pkg_b / "tests").mkdir()
    (pkg_b / "tests" / "test_b.py").write_text("def test_b(): pass\n", encoding="utf-8")

    repo_files = _list_repo_files(root)
    # Change a file in package A
    report = select_engine(root, repo_files, ["packages/a/src/core.py"])

    by_path = {s.test.path: s.priority for s in report.selections}
    assert by_path["packages/a/tests/test_a.py"] == "must"
    assert by_path["packages/b/tests/test_b.py"] == "should"


def test_package_boundary_handles_deep_nesting(tmp_path: Path) -> None:
    """The DevTrust monorepo case: src/products/<name>/code/{src,tests}/.

    A change deep under code/src/ should pull tests under code/tests/."""
    from sts.cli import _list_repo_files
    from sts.selector import select as select_engine

    root = tmp_path / "monorepo"
    code = root / "src" / "products" / "01-repo-xray" / "code"
    code.mkdir(parents=True)
    (code / "pyproject.toml").write_text('[project]\nname = "repox"\n', encoding="utf-8")
    (code / "src" / "repox").mkdir(parents=True)
    (code / "src" / "repox" / "analyzer.py").write_text("def analyze(): pass\n", encoding="utf-8")
    (code / "tests").mkdir()
    (code / "tests" / "test_smoke.py").write_text("def test_smoke(): pass\n", encoding="utf-8")

    repo_files = _list_repo_files(root)
    report = select_engine(
        root,
        repo_files,
        ["src/products/01-repo-xray/code/src/repox/analyzer.py"],
    )

    must_paths = {s.test.path for s in report.selections if s.priority == "must"}
    assert "src/products/01-repo-xray/code/tests/test_smoke.py" in must_paths


def test_cli_no_use_repox_skips_artifact(sample_repo: Path) -> None:
    """When --no-use-repox is set, sts walks the disk even if an artifact exists."""
    repox_dir = sample_repo / ".repox"
    repox_dir.mkdir()
    (repox_dir / "architecture.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "tool_version": "0.1.0",
                # If sts honored this, it would only see 1 file.
                "files": [
                    {
                        "path": "ONLY-ONE.py",
                        "language": "Python",
                        "size_bytes": 1,
                        "is_binary": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "select",
            "--repo",
            str(sample_repo),
            "--changed",
            "src/app/foo.py",
            "--no-use-repox",
            "--quiet",
        ],
    )
    assert result.exit_code == 0
    data = json.loads((sample_repo / ".sts" / "selection.json").read_text(encoding="utf-8"))
    # If --no-use-repox were honored, the file walk should still find
    # multiple tests (not just ONLY-ONE.py).
    assert data["stats"]["total_tests_in_repo"] >= 4
    assert data["inputs"]["used_repox_artifact"] is False


# ---------------------------------------------------------------------------
# v0.0.3: transitive-import affecting
# ---------------------------------------------------------------------------


def test_transitive_import_affects_test_two_hops_away(tmp_path: Path) -> None:
    """Test (test_app.py) imports app.py, which imports core.py.

    Changing core.py should make test_app.py must-run via the
    transitive heuristic with depth 2."""
    from sts.cli import _list_repo_files
    from sts.models import RepoxArtifact
    from sts.selector import select as select_engine

    root = tmp_path / "ti-repo"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "ti"\n', encoding="utf-8")
    (root / "core.py").write_text("def core(): return 1\n", encoding="utf-8")
    (root / "app.py").write_text(
        "from core import core\n\ndef app(): return core()\n",
        encoding="utf-8",
    )
    (root / "test_app.py").write_text(
        "from app import app\n\ndef test_app(): assert app() == 1\n",
        encoding="utf-8",
    )

    repo_files = _list_repo_files(root)

    # Simulate a repox artifact whose call_graph captured the imports.
    artifact = RepoxArtifact(
        paths=repo_files,
        schema_version="0.3.0",
        tool_version="0.3.0",
        imports_by_source={
            "app.py": ["core.py"],
            "test_app.py": ["app.py"],
        },
    )

    report = select_engine(root, repo_files, ["core.py"], repox_artifact=artifact)
    test_sel = next(s for s in report.selections if s.test.path == "test_app.py")
    assert test_sel.priority == "must"
    assert "transitive import" in test_sel.reason


def test_transitive_import_with_no_call_graph_falls_back(tmp_path: Path) -> None:
    """Without imports_by_source, the engine should NOT mark unrelated tests
    as must-run via this heuristic (old v0.0.2 behavior preserved)."""
    from sts.cli import _list_repo_files
    from sts.models import RepoxArtifact
    from sts.selector import select as select_engine

    root = tmp_path / "no-cg-repo"
    root.mkdir()
    (root / "packages").mkdir()
    pkg_a = root / "packages" / "a"
    pkg_a.mkdir()
    (pkg_a / "pyproject.toml").write_text('[project]\nname = "a"\n', encoding="utf-8")
    (pkg_a / "src.py").write_text("def f(): return 1\n", encoding="utf-8")

    pkg_b = root / "packages" / "b"
    pkg_b.mkdir()
    (pkg_b / "pyproject.toml").write_text('[project]\nname = "b"\n', encoding="utf-8")
    (pkg_b / "tests").mkdir()
    (pkg_b / "tests" / "test_b.py").write_text("def test_b(): pass\n", encoding="utf-8")

    repo_files = _list_repo_files(root)
    # Empty imports_by_source -> the transitive heuristic is a no-op.
    artifact = RepoxArtifact(
        paths=repo_files,
        schema_version="0.1.0",
        tool_version="0.1.0",
        imports_by_source={},
    )
    report = select_engine(root, repo_files, ["packages/a/src.py"], repox_artifact=artifact)
    # Package B's test is unrelated and not transitively imported -> should-run.
    by_path = {s.test.path: s.priority for s in report.selections}
    assert by_path["packages/b/tests/test_b.py"] == "should"


def test_repox_integration_extracts_imports_by_source(tmp_path: Path) -> None:
    """Loading a v0.3.0 architecture.json populates imports_by_source from
    the call_graph block."""
    from sts.repox_integration import load_files

    repox_dir = tmp_path / ".repox"
    repox_dir.mkdir()
    arch = {
        "schema_version": "0.3.0",
        "tool_version": "0.3.0",
        "files": [
            {"path": "core.py", "language": "Python", "size_bytes": 1, "is_binary": False},
            {"path": "app.py", "language": "Python", "size_bytes": 1, "is_binary": False},
        ],
        "call_graph": {
            "imports": [
                {
                    "source_file": "app.py",
                    "target_module": "core",
                    "target_file": "core.py",
                    "is_relative": False,
                    "line": 1,
                },
                # External imports (target_file=None) are filtered out.
                {
                    "source_file": "app.py",
                    "target_module": "os",
                    "target_file": None,
                    "is_relative": False,
                    "line": 2,
                },
            ],
            "symbols": [],
            "edges": [],
        },
    }
    (repox_dir / "architecture.json").write_text(json.dumps(arch), encoding="utf-8")

    artifact = load_files(tmp_path)
    assert artifact is not None
    assert artifact.imports_by_source == {"app.py": ["core.py"]}


def test_schema_version_for_sts_bumped_to_0_2_0() -> None:
    from sts.models import SCHEMA_VERSION

    assert SCHEMA_VERSION == "0.2.0"
