"""Shared pytest fixtures for Repo X-ray tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def sample_repo(tmp_path: Path) -> Iterator[Path]:
    """Build a small synthetic repo on disk and yield its root.

    Layout:
        sample/
            .gitignore             excludes secret.txt and dist/
            LICENSE                Apache-2.0 stub for license-detection
            package.json           name + main + dependencies + devDependencies
            pyproject.toml         [project] + [project.scripts] + dependencies
            README.md
            index.js
            main.py
            src/
                lib.py
                utils.ts
            tests/
                test_smoke.py      so conventions module sees a tests dir
            dist/
                bundled.js         ignored
            secret.txt             ignored
    """
    root = tmp_path / "sample"
    root.mkdir()

    (root / ".gitignore").write_text("dist/\nsecret.txt\n", encoding="utf-8")

    # Apache-2.0 stub - enough body for the license sniffer to catch it.
    (root / "LICENSE").write_text(
        "Apache License, Version 2.0\n\n"
        'Licensed under the Apache License, Version 2.0 (the "License");\n'
        "you may not use this file except in compliance with the License.\n",
        encoding="utf-8",
    )

    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "sample",
                "version": "1.0.0",
                "main": "index.js",
                "dependencies": {"left-pad": "^1.3.0"},
                "devDependencies": {"jest": "^29.0.0"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "sample"\n'
        'version = "0.0.1"\n'
        'requires-python = ">=3.11"\n'
        'dependencies = ["click>=8", "rich>=13"]\n\n'
        "[project.scripts]\n"
        'run = "sample.cli:main"\n\n'
        "[project.optional-dependencies]\n"
        'extra = ["httpx>=0.27"]\n\n'
        "[dependency-groups]\n"
        'dev = ["pytest>=8", "ruff"]\n',
        encoding="utf-8",
    )

    (root / "README.md").write_text("# Sample\n\nA test repo for Repo X-ray.\n", encoding="utf-8")
    (root / "index.js").write_text("console.log('hello');\n", encoding="utf-8")
    (root / "main.py").write_text("def main():\n    print('hi')\n", encoding="utf-8")

    src = root / "src"
    src.mkdir()
    (src / "lib.py").write_text("VALUE = 1\n", encoding="utf-8")
    (src / "utils.ts").write_text("export const x = 1;\n", encoding="utf-8")

    tests = root / "tests"
    tests.mkdir()
    (tests / "test_smoke.py").write_text("def test_ok(): assert True\n", encoding="utf-8")

    dist = root / "dist"
    dist.mkdir()
    (dist / "bundled.js").write_text("// bundled\n", encoding="utf-8")

    (root / "secret.txt").write_text("password123\n", encoding="utf-8")

    yield root
