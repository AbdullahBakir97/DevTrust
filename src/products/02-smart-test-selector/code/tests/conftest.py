"""Shared pytest fixtures for sts tests.

The synthetic repo here is deliberately mixed-language so we exercise the
framework detector against multiple ecosystems in one fixture.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def sample_repo(tmp_path: Path) -> Iterator[Path]:
    """Build a small synthetic mixed-language repo on disk and yield its root.

    Layout:
        sample/
            pyproject.toml
            package.json
            src/
                app/
                    foo.py
                    bar.py
                    utils.ts
            tests/
                test_foo.py        pytest, sibling-by-name to src/app/foo.py
                app/
                    test_bar.py    pytest, mirror-tree match for src/app/bar.py
            __tests__/
                utils.test.ts      jest, naming-convention for src/app/utils.ts
            cmd/
                main.go
                main_test.go       gotest, sibling
            crate/
                Cargo.toml
                src/
                    lib.rs
                tests/
                    smoke.rs       cargo
    """
    root = tmp_path / "sample"
    root.mkdir()

    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.0.1"\n', encoding="utf-8"
    )
    (root / "package.json").write_text(
        json.dumps({"name": "sample", "version": "0.0.1"}, indent=2),
        encoding="utf-8",
    )

    src_app = root / "src" / "app"
    src_app.mkdir(parents=True)
    (src_app / "foo.py").write_text("def foo(): return 1\n", encoding="utf-8")
    (src_app / "bar.py").write_text("def bar(): return 2\n", encoding="utf-8")
    (src_app / "utils.ts").write_text("export const x = 1;\n", encoding="utf-8")

    tests = root / "tests"
    tests.mkdir()
    (tests / "test_foo.py").write_text(
        "from app.foo import foo\n\ndef test_foo(): assert foo() == 1\n",
        encoding="utf-8",
    )
    (tests / "app").mkdir()
    (tests / "app" / "test_bar.py").write_text("def test_bar(): pass\n", encoding="utf-8")

    jest_dir = root / "__tests__"
    jest_dir.mkdir()
    (jest_dir / "utils.test.ts").write_text(
        "test('utils', () => { /* jest */ });\n", encoding="utf-8"
    )

    go_dir = root / "cmd"
    go_dir.mkdir()
    # go.mod marks `cmd/` as its own package, so the package-boundary
    # heuristic correctly scopes its tests separately from the root pyproject.
    (go_dir / "go.mod").write_text("module example.com/cmd\n\ngo 1.22\n", encoding="utf-8")
    (go_dir / "main.go").write_text("package main\n", encoding="utf-8")
    (go_dir / "main_test.go").write_text(
        'package main\nimport "testing"\nfunc TestMain(t *testing.T) {}\n',
        encoding="utf-8",
    )

    crate = root / "crate"
    crate.mkdir()
    (crate / "Cargo.toml").write_text(
        '[package]\nname = "sample"\nversion = "0.0.1"\n', encoding="utf-8"
    )
    (crate / "src").mkdir()
    (crate / "src" / "lib.rs").write_text("pub fn add() -> u8 { 1 }\n", encoding="utf-8")
    (crate / "tests").mkdir()
    (crate / "tests" / "smoke.rs").write_text("fn main() {}\n", encoding="utf-8")

    yield root
