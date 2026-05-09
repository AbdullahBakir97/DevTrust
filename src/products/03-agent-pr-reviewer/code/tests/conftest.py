"""Shared pytest fixtures for apr tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def py_repo(tmp_path: Path) -> Iterator[Path]:
    """A small Python repo we can fire rules at."""
    root = tmp_path / "py"
    root.mkdir()
    (root / "good.py").write_text(
        "def helper() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    (root / "bare_except.py").write_text(
        "def boom() -> int:\n    try:\n        return 1 / 0\n    except:\n        return -1\n",
        encoding="utf-8",
    )
    (root / "todo_no_ticket.py").write_text(
        "# TODO: refactor this when we have time\n"
        "# TODO #42: this one is fine\n"
        "def stub() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (root / "syntax_broken.py").write_text(
        "def oh no(:\n",
        encoding="utf-8",
    )
    (root / "debug_print.py").write_text(
        "def f() -> None:\n    print('debugging')\n",
        encoding="utf-8",
    )
    yield root


@pytest.fixture
def js_repo(tmp_path: Path) -> Iterator[Path]:
    """A small JS/TS repo we can fire the JS rule pack at."""
    root = tmp_path / "js"
    root.mkdir()
    (root / "good.ts").write_text(
        "export const add = (a: number, b: number): number => a + b;\n",
        encoding="utf-8",
    )
    (root / "console_log.ts").write_text(
        "export function f(): void {\n  console.log('debugging here');\n}\n",
        encoding="utf-8",
    )
    (root / "debugger_stmt.ts").write_text(
        "export function f(): void {\n  debugger;\n  return;\n}\n",
        encoding="utf-8",
    )
    (root / "var_decl.js").write_text(
        "var x = 1;\nfunction f() { return x; }\n",
        encoding="utf-8",
    )
    (root / "todo_no_ticket.ts").write_text(
        "// TODO: refactor when there's time\n// TODO #42: this one is fine\nexport const x = 1;\n",
        encoding="utf-8",
    )
    # An "entry" file -- presence of process.argv should suppress console-log
    (root / "cli.js").write_text(
        "if (process.argv.length > 2) {\n  console.log('args:', process.argv);\n}\n",
        encoding="utf-8",
    )
    yield root


@pytest.fixture
def py_secret_repo(tmp_path: Path) -> Iterator[Path]:
    """Repo with a deliberately-leaked secret-looking value, for the
    hardcoded-secret rule. Uses an obviously-fake test value."""
    root = tmp_path / "secrets"
    root.mkdir()
    # A clearly-fake AWS key (right shape, never valid). The rule
    # matches on shape, not whether the key is real.
    (root / "leak.py").write_text(
        'AWS_KEY = "AKIA' + "X" * 16 + '"\n',
        encoding="utf-8",
    )
    (root / "clean.py").write_text(
        'import os\nAWS_KEY = os.environ["AWS_KEY"]\n',
        encoding="utf-8",
    )
    yield root
