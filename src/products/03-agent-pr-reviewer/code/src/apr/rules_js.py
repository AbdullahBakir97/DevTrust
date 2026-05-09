"""Tree-sitter-based JS/TS rule pack.

What v0.0.2 catches:

  - `console-log` (info, ai-pattern):
        leftover `console.log(...)` debug output. Skipped in obvious
        CLI/server entry files (presence of `process.argv` or top-level
        `app.listen`).
  - `debugger-statement` (warning, quality):
        `debugger;` left in code -- breaks the page/server in real users.
  - `var-declaration` (info, style):
        `var x = ...` instead of `let`/`const`. ES6+ codebases should
        prefer block-scoped declarations.
  - `todo-no-ticket` (info, todo):
        TODO/FIXME/XXX/HACK comment without a `#123` or `PROJ-123`
        reference. Mirror of the Python rule.

Tree-sitter is a required dep (graduated from optional in repox v0.3).
If the wheels still fail to load on a particular platform, this module
falls back to "no findings" rather than crashing the engine.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from apr.models import Finding

# Mapping extension -> tree-sitter language id (matches repox.callgraph_ts)
_EXT_LANG: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}


_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b(?P<rest>[^\n]*)", re.IGNORECASE)
_TICKET_RE = re.compile(r"(?:#|[A-Z]{2,}-)\d+")


def _node_text(node: Any, source: bytes) -> str:
    """Return the source text of a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _is_entry_file_indicator(source: bytes) -> bool:
    """True if the source looks like a CLI / server entry point.

    Heuristic, but precise enough: we skip console-log only when one of
    these appears, so false-positives (still flagging debug logs in a
    legit CLI) are rare and acceptable.
    """
    text = source.decode("utf-8", errors="replace")
    return "process.argv" in text or ".listen(" in text or "import.meta.main" in text


def _walk(node: Any, on_node: Any) -> None:
    """Pre-order tree walk."""
    on_node(node)
    for child in node.children:
        _walk(child, on_node)


def check_js_file(rel_path: str, source: bytes, parser: Any) -> list[Finding]:
    """Run the JS/TS rule pack against one file."""
    try:
        tree = parser.parse(source)
    except Exception:
        return []

    findings: list[Finding] = []
    skip_console_log = _is_entry_file_indicator(source)

    def visit(node: Any) -> None:
        ntype = node.type
        line = node.start_point[0] + 1

        # console.log / console.debug / console.info
        if ntype == "call_expression" and not skip_console_log:
            children = node.children
            if children and children[0].type == "member_expression":
                me = children[0]
                me_text = _node_text(me, source)
                if me_text.startswith(("console.log", "console.debug", "console.info")):
                    findings.append(
                        Finding(
                            rule_id="console-log",
                            severity="info",
                            category="quality",
                            message=(
                                f"`{me_text.split('(')[0]}` looks like leftover debug output."
                            ),
                            file=rel_path,
                            line=line,
                            suggestion=("Remove before merge or replace with a structured logger."),
                        )
                    )

        # `debugger;`
        if ntype == "debugger_statement":
            findings.append(
                Finding(
                    rule_id="debugger-statement",
                    severity="warning",
                    category="quality",
                    message="`debugger;` left in code; will break runtime.",
                    file=rel_path,
                    line=line,
                    suggestion="Remove before merge.",
                )
            )

        # `var x = ...`
        if ntype == "variable_declaration":
            # tree-sitter-javascript distinguishes lexical_declaration
            # (let/const) from variable_declaration (var). Confirm with
            # the leading keyword text just to be safe.
            children = node.children
            if children and children[0].type == "var":
                findings.append(
                    Finding(
                        rule_id="var-declaration",
                        severity="info",
                        category="style",
                        message=("`var` is function-scoped and hoisted; prefer `let` or `const`."),
                        file=rel_path,
                        line=line,
                    )
                )

    _walk(tree.root_node, visit)

    # Comment-based rules: tree-sitter exposes comments as nodes too,
    # but a regex scan is just as accurate and language-agnostic.
    for i, line_text in enumerate(source.decode("utf-8", errors="replace").splitlines(), start=1):
        m = _TODO_RE.search(line_text)
        if m is None:
            continue
        rest = m.group("rest") or ""
        if _TICKET_RE.search(rest):
            continue
        findings.append(
            Finding(
                rule_id="todo-no-ticket",
                severity="info",
                category="todo",
                message=(
                    f"`{m.group(1).upper()}` without a ticket reference "
                    f"(e.g. `#123` or `PROJ-123`)."
                ),
                file=rel_path,
                line=i,
                suggestion=("Link to a tracked issue so the TODO can be triaged later."),
            )
        )

    return findings


def _build_parsers() -> dict[str, Any]:
    """Build a parser per language we support. Empty dict if tree-sitter
    isn\'t installed -- the caller treats that as "no JS findings"."""
    try:
        from tree_sitter import Parser
        from tree_sitter_language_pack import get_language
    except ImportError:
        return {}

    parsers: dict[str, Any] = {}
    for lang_id in {"javascript", "typescript", "tsx"}:
        try:
            parsers[lang_id] = Parser(get_language(cast(Any, lang_id)))
        except Exception:
            continue
    return parsers


def check_file(repo_root: Path, rel_path: str) -> list[Finding]:
    """Top-level dispatcher for one JS/TS file. Returns [] if not JS/TS
    or if tree-sitter isn\'t available."""
    ext = "." + rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
    lang_id = _EXT_LANG.get(ext)
    if lang_id is None:
        return []

    parsers = _build_parsers()
    parser = parsers.get(lang_id)
    if parser is None:
        return []

    full = repo_root / rel_path
    try:
        source = full.read_bytes()
    except OSError:
        return []
    return check_js_file(rel_path, source, parser)
