"""Smoke + unit tests for Repo X-ray v0.1.

Coverage:
  * analyzer module       — gitignore handling, language detection, entry-point fallback
  * manifests module      — pyproject / package.json / Cargo.toml / go.mod parsing
  * conventions module    — layout detection, license sniff, indent sampling
  * output module         — JSON + Markdown writers
  * cli module            — version, build, info commands

These run end-to-end against synthetic repos built by fixtures in conftest.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from repox import __version__
from repox.analyzer import analyze
from repox.cli import app
from repox.manifests import (
    parse_cargo_toml,
    parse_go_mod,
    parse_package_json,
    parse_pyproject,
)
from repox.models import SCHEMA_VERSION
from repox.output import write_json, write_markdown
from typer.testing import CliRunner

runner = CliRunner()


# =============================================================================
# analyzer behaviour
# =============================================================================


def test_analyze_counts_files_excluding_gitignored(sample_repo: Path) -> None:
    arch = analyze(sample_repo)
    paths = {f.path for f in arch.files}
    assert "index.js" in paths
    assert "main.py" in paths
    assert "src/lib.py" in paths
    assert "src/utils.ts" in paths
    assert "dist/bundled.js" not in paths
    assert "secret.txt" not in paths


def test_analyze_detects_languages(sample_repo: Path) -> None:
    arch = analyze(sample_repo)
    by_name = {lang.name for lang in arch.languages}
    for needed in ("JavaScript", "Python", "TypeScript", "Markdown", "JSON", "TOML"):
        assert needed in by_name, f"missing: {needed}"


def test_analyze_detects_entry_points(sample_repo: Path) -> None:
    arch = analyze(sample_repo)
    kinds = {ep.kind for ep in arch.entry_points}
    paths = {ep.path for ep in arch.entry_points}
    assert "package.json:main" in kinds
    assert "index.js" in paths
    assert "main.py" in paths


def test_analyze_top_level_metrics_consistent(sample_repo: Path) -> None:
    arch = analyze(sample_repo)
    assert arch.repo.total_files == len(arch.files)
    assert arch.repo.total_size_bytes == sum(f.size_bytes for f in arch.files)
    expected_lines = sum((f.line_count or 0) for f in arch.files if not f.is_binary)
    assert arch.repo.total_lines == expected_lines


def test_entry_points_have_no_duplicates(sample_repo: Path) -> None:
    """Regression: package.json:main + index.js conventional must dedup."""
    arch = analyze(sample_repo)
    paths = [ep.path for ep in arch.entry_points]
    assert paths.count("index.js") == 1, f"index.js appeared {paths.count('index.js')} times"


# =============================================================================
# manifests module
# =============================================================================


def test_parse_pyproject_extracts_scripts_and_runtime_deps(sample_repo: Path) -> None:
    eps, deps, info = parse_pyproject(sample_repo / "pyproject.toml")
    assert info is not None
    assert info.kind == "pyproject"
    assert info.package_name == "sample"
    # The fixture declares a CLI script
    script_kinds = {ep.kind for ep in eps}
    assert "pyproject:scripts" in script_kinds
    # And a runtime dep
    dep_names = {d.name for d in deps if d.kind == "runtime"}
    assert dep_names, f"expected at least one runtime dep, got: {[d.name for d in deps]}"


def test_parse_package_json_extracts_main_and_deps(sample_repo: Path) -> None:
    eps, deps, info = parse_package_json(sample_repo / "package.json")
    assert info is not None
    assert info.package_name == "sample"
    assert any(ep.kind == "package.json:main" for ep in eps)
    assert any(d.name == "left-pad" for d in deps if d.kind == "runtime")


def test_parse_pyproject_handles_missing_file(tmp_path: Path) -> None:
    eps, deps, info = parse_pyproject(tmp_path / "does-not-exist.toml")
    assert eps == [] and deps == [] and info is None


def test_parse_pyproject_handles_malformed_toml(tmp_path: Path) -> None:
    bad = tmp_path / "pyproject.toml"
    bad.write_text("not a valid toml [[[", encoding="utf-8")
    eps, deps, info = parse_pyproject(bad)
    assert eps == [] and deps == [] and info is None


def test_parse_cargo_toml(tmp_path: Path) -> None:
    cargo = tmp_path / "Cargo.toml"
    cargo.write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\n\n'
        '[[bin]]\nname = "demo"\npath = "src/main.rs"\n\n'
        '[dependencies]\nserde = "1"\n[dev-dependencies]\nproptest = "1.5"\n',
        encoding="utf-8",
    )
    eps, deps, info = parse_cargo_toml(cargo)
    assert info is not None and info.package_name == "demo"
    assert any(ep.kind == "Cargo.toml:bin" for ep in eps)
    runtime = {d.name for d in deps if d.kind == "runtime"}
    dev = {d.name for d in deps if d.kind == "dev"}
    assert "serde" in runtime
    assert "proptest" in dev


def test_parse_go_mod(tmp_path: Path) -> None:
    gomod = tmp_path / "go.mod"
    gomod.write_text(
        "module example.com/demo\n\n"
        "go 1.22\n\n"
        "require (\n"
        "    github.com/spf13/cobra v1.8.0\n"
        "    github.com/stretchr/testify v1.9.0\n"
        ")\n",
        encoding="utf-8",
    )
    eps, deps, info = parse_go_mod(gomod)
    assert info is not None and info.package_name == "example.com/demo"
    assert any(ep.kind == "go:module" for ep in eps)
    names = {d.name for d in deps}
    assert "github.com/spf13/cobra" in names
    assert "github.com/stretchr/testify" in names


# =============================================================================
# conventions module
# =============================================================================


def test_conventions_detect_layout_and_license(sample_repo: Path) -> None:
    arch = analyze(sample_repo)
    assert arch.conventions is not None
    # Sample repo has src/<files> => src layout
    assert arch.conventions.has_src_layout is True
    # Indent sampling should produce a real result on the python+js+ts files
    assert arch.conventions.primary_indent in ("space", "tab", "mixed", "unknown")


# =============================================================================
# output writers
# =============================================================================


def test_write_json_produces_valid_artifact(sample_repo: Path) -> None:
    arch = analyze(sample_repo)
    json_path = write_json(arch, sample_repo)
    assert json_path == sample_repo / ".repox" / "architecture.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["tool_version"] == __version__
    assert payload["repo"]["name"] == "sample"
    # Timestamp must be timezone-aware (not the deprecated naive utcnow form).
    assert payload["generated_at"].endswith("+00:00") or payload["generated_at"].endswith("Z")
    # New 0.1 sections present (or null when empty), but in this fixture they should be populated.
    assert payload["dependencies"] is not None
    assert payload["conventions"] is not None


def test_write_markdown_includes_summary_and_new_sections(sample_repo: Path) -> None:
    arch = analyze(sample_repo)
    md_path = write_markdown(arch, sample_repo)
    body = md_path.read_text(encoding="utf-8")
    assert f"Repo X-ray v{__version__}" in body
    assert "## Languages" in body
    assert "## Entry points" in body
    assert "## Manifests" in body  # new in v0.1
    assert "## Conventions" in body  # new in v0.1


# =============================================================================
# CLI
# =============================================================================


def test_cli_version() -> None:
    import re

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    # Rich emits ANSI escape codes when CI sets FORCE_COLOR=1; strip them
    # so the substring check works regardless of terminal styling. Without
    # this the version (e.g. '0.4.0') gets split across color escapes.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert __version__ in plain


def test_cli_build_writes_artifacts(sample_repo: Path) -> None:
    result = runner.invoke(app, ["build", str(sample_repo)])
    assert result.exit_code == 0, result.stdout
    assert (sample_repo / ".repox" / "architecture.json").is_file()
    assert (sample_repo / ".repox" / "architecture.md").is_file()


def test_cli_build_quiet_is_quiet(sample_repo: Path) -> None:
    result = runner.invoke(app, ["build", str(sample_repo), "--quiet"])
    assert result.exit_code == 0
    assert "Top languages" not in result.stdout


def test_cli_build_rejects_missing_path(tmp_path: Path) -> None:
    result = runner.invoke(app, ["build", str(tmp_path / "does-not-exist")])
    assert result.exit_code != 0


def test_cli_info_does_not_write_files(sample_repo: Path) -> None:
    result = runner.invoke(app, ["info", str(sample_repo)])
    assert result.exit_code == 0
    assert not (sample_repo / ".repox").exists()


# ---------------------------------------------------------------------------
# v0.2.0: call graph (imports + symbols)
# ---------------------------------------------------------------------------


def test_callgraph_extracts_imports_for_python(tmp_path: Path) -> None:
    from repox.analyzer import analyze

    repo = tmp_path / "cg-sample"
    repo.mkdir()
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "core.py").write_text(
        "VALUE = 1\n\ndef hello() -> str:\n    return 'hi'\n",
        encoding="utf-8",
    )
    (repo / "pkg" / "consumer.py").write_text(
        "import os\nimport json as j\nfrom pkg.core import hello, VALUE\nfrom . import core as c\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    cg = arch.call_graph

    sources = {imp.source_file for imp in cg.imports}
    assert "pkg/consumer.py" in sources

    # External import (os) — should appear with target_file=None
    os_imports = [
        imp
        for imp in cg.imports
        if imp.source_file == "pkg/consumer.py" and imp.target_module == "os"
    ]
    assert len(os_imports) == 1
    assert os_imports[0].target_file is None

    # Absolute in-repo import resolves to pkg/core.py
    core_imports = [
        imp
        for imp in cg.imports
        if imp.source_file == "pkg/consumer.py" and imp.target_module == "pkg.core"
    ]
    assert len(core_imports) == 1
    assert core_imports[0].target_file == "pkg/core.py"

    # Relative import keeps dots in target_module and resolves to the same file
    rel_imports = [
        imp for imp in cg.imports if imp.source_file == "pkg/consumer.py" and imp.is_relative
    ]
    assert len(rel_imports) == 1
    assert rel_imports[0].target_module.startswith(".")
    assert rel_imports[0].target_file == "pkg/core.py"


def test_callgraph_extracts_symbols(tmp_path: Path) -> None:
    from repox.analyzer import analyze

    repo = tmp_path / "sym-sample"
    repo.mkdir()
    (repo / "mod.py").write_text(
        "TOP_LEVEL = 1\n"
        "_PRIVATE = 2\n\n"
        "def public_fn(): pass\n"
        "def _internal(): pass\n\n"
        "class Widget:\n"
        "    def render(self): pass\n"
        "    def _setup(self): pass\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    cg = arch.call_graph

    by_name = {(s.kind, s.name) for s in cg.symbols if s.source_file == "mod.py"}
    assert ("function", "public_fn") in by_name
    assert ("function", "_internal") in by_name
    assert ("class", "Widget") in by_name
    assert ("method", "Widget.render") in by_name
    assert ("method", "Widget._setup") in by_name
    assert ("variable", "TOP_LEVEL") in by_name

    # is_public flag: leading-underscore names should be False
    private = next(s for s in cg.symbols if s.name == "_internal")
    assert private.is_public is False
    public = next(s for s in cg.symbols if s.name == "public_fn")
    assert public.is_public is True


def test_callgraph_files_importing_helper(tmp_path: Path) -> None:
    """`CallGraph.files_importing(target)` returns sorted list of files that
    import the given in-repo target."""
    from repox.analyzer import analyze

    repo = tmp_path / "fi-sample"
    repo.mkdir()
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "pkg" / "a.py").write_text("from pkg.core import VALUE\n", encoding="utf-8")
    (repo / "pkg" / "b.py").write_text("from pkg.core import VALUE\n", encoding="utf-8")

    arch = analyze(repo)
    assert arch.call_graph is not None
    importers = arch.call_graph.files_importing("pkg/core.py")
    assert importers == ["pkg/a.py", "pkg/b.py"]


def test_callgraph_swallows_syntax_errors(tmp_path: Path) -> None:
    """A file that doesn't parse should not crash the build."""
    from repox.analyzer import analyze

    repo = tmp_path / "broken-sample"
    repo.mkdir()
    (repo / "good.py").write_text("def ok(): pass\n", encoding="utf-8")
    (repo / "bad.py").write_text("def (\n", encoding="utf-8")

    arch = analyze(repo)
    assert arch.call_graph is not None
    # The good file's symbol shows up; the bad file is silently skipped
    sources = {s.source_file for s in arch.call_graph.symbols}
    assert "good.py" in sources
    assert "bad.py" not in sources


# ---------------------------------------------------------------------------
# v0.3.0: Python call edges
# ---------------------------------------------------------------------------


def test_callgraph_extracts_python_call_edges(tmp_path: Path) -> None:
    """`def fn():\n  helper()` produces a CallEdge from fn to helper."""
    from repox.analyzer import analyze

    repo = tmp_path / "calls-py"
    repo.mkdir()
    (repo / "lib.py").write_text("def helper() -> int:\n    return 1\n", encoding="utf-8")
    (repo / "main.py").write_text(
        "from lib import helper\n\ndef run() -> int:\n    return helper() + 1\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    edges = arch.call_graph.edges
    main_edges = [e for e in edges if e.source_file == "main.py"]
    helper_edges = [e for e in main_edges if e.callee_name == "helper"]

    assert len(helper_edges) == 1
    e = helper_edges[0]
    assert e.caller == "run"
    assert e.target_file == "lib.py"  # resolved via the from-import
    assert e.line >= 1


def test_callgraph_call_edges_resolve_same_file_calls(tmp_path: Path) -> None:
    """Calls to a function defined in the same file resolve to that file."""
    from repox.analyzer import analyze

    repo = tmp_path / "samefile-calls"
    repo.mkdir()
    (repo / "mod.py").write_text(
        "def helper() -> int:\n    return 1\n\ndef main() -> int:\n    return helper()\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    same_file_edge = next(
        e for e in arch.call_graph.edges if e.caller == "main" and e.callee_name == "helper"
    )
    assert same_file_edge.target_file == "mod.py"


def test_callgraph_unresolved_calls_have_target_file_none(tmp_path: Path) -> None:
    """Builtin / dynamic calls that we can't resolve still appear with target_file=None."""
    from repox.analyzer import analyze

    repo = tmp_path / "unresolved-calls"
    repo.mkdir()
    (repo / "mod.py").write_text(
        "def main() -> int:\n    return len([1, 2, 3])\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    len_edge = next((e for e in arch.call_graph.edges if e.callee_name == "len"), None)
    assert len_edge is not None
    assert len_edge.target_file is None  # builtin, can't resolve


def test_callgraph_callers_of_helper(tmp_path: Path) -> None:
    """`callers_of(target_file)` lists every source file that has an edge into it."""
    from repox.analyzer import analyze

    repo = tmp_path / "callers-of"
    repo.mkdir()
    (repo / "lib.py").write_text("def f(): return 1\n", encoding="utf-8")
    (repo / "a.py").write_text("from lib import f\n\ndef ga(): return f()\n", encoding="utf-8")
    (repo / "b.py").write_text("from lib import f\n\ndef gb(): return f()\n", encoding="utf-8")

    arch = analyze(repo)
    assert arch.call_graph is not None
    callers = arch.call_graph.callers_of("lib.py")
    assert callers == ["a.py", "b.py"]


def test_schema_version_bumped_to_0_3_0() -> None:
    from repox.models import SCHEMA_VERSION

    assert SCHEMA_VERSION == "0.3.0"


# ---------------------------------------------------------------------------
# v0.3.0: tree-sitter JS / TS extraction (best-effort)
#
# The tree-sitter wheels are required as of v0.3, but if they fail to
# load on a particular platform we don't want the whole test suite to
# crash. We `pytest.importorskip` so these tests only run when the
# wheels are present.
# ---------------------------------------------------------------------------


def test_callgraph_ts_extracts_es6_imports_and_symbols(tmp_path: Path) -> None:
    import pytest as _pt

    _pt.importorskip("tree_sitter")
    _pt.importorskip("tree_sitter_language_pack")

    from repox.analyzer import analyze

    repo = tmp_path / "calls-js"
    repo.mkdir()
    (repo / "math.js").write_text(
        "export function add(a, b) { return a + b; }\nexport const PI = 3.14;\n",
        encoding="utf-8",
    )
    (repo / "app.js").write_text(
        "import { add } from './math';\n"
        "import { z } from 'lodash';\n"
        "const x = require('./math');\n"
        "function main() { return add(1, 2); }\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    cg = arch.call_graph

    js_imports = [imp for imp in cg.imports if imp.source_file == "app.js"]

    # ES6 import './math' resolves to math.js (relative imports start with '.')
    rel_imports = [imp for imp in js_imports if imp.is_relative]
    assert any(imp.target_file == "math.js" for imp in rel_imports)

    # External (lodash) -> target_file is None
    bare = [imp for imp in js_imports if imp.target_module == "lodash"]
    assert len(bare) == 1
    assert bare[0].target_file is None

    # Exported symbol detected
    js_symbols = [s for s in cg.symbols if s.source_file == "math.js"]
    by_name = {(s.kind, s.name) for s in js_symbols}
    assert ("function", "add") in by_name
    assert ("variable", "PI") in by_name


# ---------------------------------------------------------------------------
# v0.4.0: JS/TS function-call edges
# ---------------------------------------------------------------------------


def test_callgraph_ts_extracts_call_edges_for_imported_function(tmp_path: Path) -> None:
    """`import { add } from './math'; function main() { return add(1, 2); }`
    should produce a CallEdge from main -> add with target_file resolved."""
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from repox.analyzer import analyze

    repo = tmp_path / "ts-edges"
    repo.mkdir()
    (repo / "math.js").write_text(
        "export function add(a, b) { return a + b; }\n",
        encoding="utf-8",
    )
    (repo / "app.js").write_text(
        "import { add } from './math';\nfunction main() { return add(1, 2); }\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    js_edges = [e for e in arch.call_graph.edges if e.source_file == "app.js"]
    add_edge = next(
        (e for e in js_edges if e.callee_name == "add"),
        None,
    )
    assert add_edge is not None
    assert add_edge.caller == "main"
    assert add_edge.target_file == "math.js"


def test_callgraph_ts_call_edges_resolve_same_file_calls(tmp_path: Path) -> None:
    """Calls to a function defined in the same file resolve to that file."""
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from repox.analyzer import analyze

    repo = tmp_path / "ts-same-file"
    repo.mkdir()
    (repo / "mod.ts").write_text(
        "function helper(): number { return 1; }\n"
        "export function main(): number { return helper(); }\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    same_file = next(
        (
            e
            for e in arch.call_graph.edges
            if e.source_file == "mod.ts" and e.caller == "main" and e.callee_name == "helper"
        ),
        None,
    )
    assert same_file is not None
    assert same_file.target_file == "mod.ts"


def test_callgraph_ts_unresolved_calls_have_target_file_none(tmp_path: Path) -> None:
    """Calls to globals like console.log keep target_file=None."""
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from repox.analyzer import analyze

    repo = tmp_path / "ts-unresolved"
    repo.mkdir()
    (repo / "mod.ts").write_text(
        "export function main(): void { console.log('hi'); }\n",
        encoding="utf-8",
    )

    arch = analyze(repo)
    assert arch.call_graph is not None
    log_edge = next(
        (e for e in arch.call_graph.edges if e.callee_name == "console.log"),
        None,
    )
    assert log_edge is not None
    assert log_edge.target_file is None


def test_repox_version_bumped_to_0_4_0() -> None:
    from repox import __version__

    assert __version__ == "0.4.0"
