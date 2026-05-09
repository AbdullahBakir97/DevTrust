"""Lightweight conventions extraction.

For v0.1 we extract only what's visible from file structure plus a few
configuration files. Deep convention learning (naming patterns from AST,
error-handling style, etc.) is a v0.2 feature once tree-sitter is wired in.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from repox.models import Conventions, IndentStyle

# Files that signal "this is a structured project" - we surface them in the
# conventions report so downstream tools know what tooling the repo uses.
KNOWN_CONFIG_FILES: set[str] = {
    ".editorconfig",
    ".gitignore",
    ".gitattributes",
    ".pre-commit-config.yaml",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.yaml",
    ".prettierrc.yml",
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.yaml",
    ".eslintrc.yml",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".stylelintrc",
    ".stylelintrc.json",
    ".rubocop.yml",
    ".golangci.yml",
    ".golangci.yaml",
    "rustfmt.toml",
    ".rustfmt.toml",
    "biome.json",
    "biome.jsonc",
    "tsconfig.json",
    "ruff.toml",
    ".ruff.toml",
    "mypy.ini",
    ".mypy.ini",
    "pytest.ini",
    "tox.ini",
    "noxfile.py",
    "Makefile",
    "makefile",
    "GNUmakefile",
    "Justfile",
    "justfile",
    "renovate.json",
    "renovate.json5",
    "dependabot.yml",
    ".dockerignore",
    "docker-compose.yml",
    "docker-compose.yaml",
    "vite.config.ts",
    "vite.config.js",
    "vite.config.mjs",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "astro.config.mjs",
    "astro.config.ts",
    "svelte.config.js",
    "tailwind.config.js",
    "tailwind.config.ts",
    "tailwind.config.mjs",
    "playwright.config.ts",
    "playwright.config.js",
    "vitest.config.ts",
    "vitest.config.js",
    "jest.config.js",
    "jest.config.ts",
    "jest.config.mjs",
}

LICENSE_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bApache\s+License,?\s+Version\s+2", re.IGNORECASE), "Apache-2.0"),
    (re.compile(r"\bMIT License\b", re.IGNORECASE), "MIT"),
    (re.compile(r"\bGNU GENERAL PUBLIC LICENSE\s+Version\s+3", re.IGNORECASE), "GPL-3.0"),
    (re.compile(r"\bGNU GENERAL PUBLIC LICENSE\s+Version\s+2", re.IGNORECASE), "GPL-2.0"),
    (re.compile(r"\bBSD 3-Clause License\b", re.IGNORECASE), "BSD-3-Clause"),
    (re.compile(r"\bBSD 2-Clause License\b", re.IGNORECASE), "BSD-2-Clause"),
    (re.compile(r"\bMozilla Public License\s+Version\s+2", re.IGNORECASE), "MPL-2.0"),
    (re.compile(r"\bThe Unlicense\b", re.IGNORECASE), "Unlicense"),
    (re.compile(r"\bCC0\b", re.IGNORECASE), "CC0-1.0"),
]

INDENT_SAMPLE_EXTS: set[str] = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".rs",
    ".go",
    ".rb",
    ".java",
    ".cs",
}
MAX_INDENT_SAMPLE_FILES = 50


def _detect_license(root: Path) -> str | None:
    """Sniff the root LICENSE / LICENSE.txt / LICENSE.md for a known license."""
    for candidate in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt"):
        path = root / candidate
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")[:8000]
            except OSError:
                continue
            for pattern, spdx in LICENSE_HINTS:
                if pattern.search(content):
                    return spdx
            # Filename gives a hint but no body match - return the filename
            return candidate
    return None


def _sample_indent(path: Path) -> tuple[str, int] | None:
    """Look at the first ~30 lines of a file to guess indent style.

    Returns ('space', N), ('tab', N), ('mixed', N), or None if no leading
    whitespace was observed at all.
    """
    try:
        with path.open(encoding="utf-8", errors="ignore") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= 30:
                    break
                lines.append(line)
    except OSError:
        return None

    space_widths: list[int] = []
    tab_lines = 0
    for line in lines:
        if line.startswith("\t"):
            tab_lines += 1
            continue
        m = re.match(r"^( +)", line)
        if m:
            space_widths.append(len(m.group(1)))

    if not space_widths and tab_lines == 0:
        return None
    if tab_lines and not space_widths:
        return ("tab", 1)
    if space_widths and not tab_lines:
        widths = [w for w in space_widths if w > 0]
        if not widths:
            return None
        gcd_candidates = [2, 4, 8]
        scored = {g: sum(1 for w in widths if w % g == 0) for g in gcd_candidates}
        best = max(scored, key=lambda g: (scored[g], -g))
        return ("space", best)
    return ("mixed", 0)


def extract(root: Path, file_paths: list[str]) -> Conventions:
    """Build a Conventions snapshot from observable file structure.

    `file_paths` is the (already-gitignore-filtered) list of relative paths
    from `repox.analyzer`. We walk it instead of re-scanning the disk.
    """
    name_set = {p.split("/")[0] for p in file_paths if "/" in p}
    name_set |= {p for p in file_paths if "/" not in p}

    has_tests = any(p in {"tests", "test", "__tests__", "spec"} for p in name_set)
    has_docs = any(p in {"docs", "doc", "documentation"} for p in name_set)
    has_src_layout = "src" in name_set and any(p.startswith("src/") for p in file_paths)

    config_present = sorted({p for p in file_paths if "/" not in p and p in KNOWN_CONFIG_FILES})

    license_id = _detect_license(root)

    indent_styles: Counter[str] = Counter()
    indent_widths: Counter[int] = Counter()
    samples_taken = 0
    for rel in file_paths:
        if samples_taken >= MAX_INDENT_SAMPLE_FILES:
            break
        ext = "." + rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
        if ext not in INDENT_SAMPLE_EXTS:
            continue
        result = _sample_indent(root / rel)
        if result is None:
            continue
        style, width = result
        indent_styles[style] += 1
        if style == "space":
            indent_widths[width] += 1
        samples_taken += 1

    primary_indent: IndentStyle
    indent_width: int | None
    if not indent_styles:
        primary_indent = "unknown"
        indent_width = None
    else:
        primary_indent_str = indent_styles.most_common(1)[0][0]
        if primary_indent_str == "space":
            primary_indent = "space"
        elif primary_indent_str == "tab":
            primary_indent = "tab"
        else:
            primary_indent = "mixed"
        indent_width = indent_widths.most_common(1)[0][0] if indent_widths else None

    return Conventions(
        primary_indent=primary_indent,
        indent_width=indent_width,
        has_tests_dir=has_tests,
        has_docs_dir=has_docs,
        has_src_layout=has_src_layout,
        primary_license=license_id,
        config_files=config_present,
    )
