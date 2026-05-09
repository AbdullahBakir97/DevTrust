"""Deterministic rule checks for v0.0.1 of Agent-PR Reviewer.

Each `check_*` function returns a list of `Finding`s. The orchestrator
in `engine.py` decides which checks to run for which files, dedupes
findings, and assembles them into a `ReviewReport`.

Why deterministic-first:

  - Easy to grade. We can grow a dataset of "this PR / these findings"
    examples and use them to evaluate any future LLM-backed checker.
  - Predictable in CI. A team can confidently set "block on
    severity>=error" once the rule set is stable.
  - Cheap. Sub-second on big repos; no LLM token spend.

LLM-backed review (rule_id="ai-review:*") will be layered on top in v0.1+.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from apr.models import Finding

# ---------------------------------------------------------------------------
# Python source rules
# ---------------------------------------------------------------------------


def check_python_file(rel_path: str, source: str) -> list[Finding]:
    """Run the Python rule pack against one file's source.

    Source-text rules (TODO scanning, secret scanning) run regardless
    of whether the file parses. AST-based rules need a successful
    parse and are skipped when there's a syntax error.
    """
    findings: list[Finding] = []

    # 1) Source-text rules first - they don't need a parsed AST and
    #    we still want them to fire on broken files (a hardcoded secret
    #    in unparseable code is still a leaked secret).
    findings.extend(_check_todo_no_ticket(rel_path, source))
    findings.extend(_check_hardcoded_secret(rel_path, source))

    # 2) AST-based rules - need a successful parse.
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as exc:
        findings.append(
            Finding(
                rule_id="syntax-error",
                severity="error",
                category="quality",
                message=f"Python file does not parse: {exc.msg}",
                file=rel_path,
                line=exc.lineno,
            )
        )
        return findings

    findings.extend(_check_bare_except(rel_path, tree))
    findings.extend(_check_print_debug(rel_path, tree, source))
    findings.extend(_check_pass_only_function(rel_path, tree))
    findings.extend(_check_mutable_default_arg(rel_path, tree))
    findings.extend(_check_broad_except(rel_path, tree))
    findings.extend(_check_assert_in_prod_code(rel_path, tree))
    return findings


def _check_bare_except(rel_path: str, tree: ast.AST) -> list[Finding]:
    """`except:` without an exception type swallows everything, including
    KeyboardInterrupt and SystemExit. Almost always wrong."""
    out: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            out.append(
                Finding(
                    rule_id="bare-except",
                    severity="warning",
                    category="quality",
                    message="bare `except:` swallows all exceptions including KeyboardInterrupt.",
                    file=rel_path,
                    line=node.lineno,
                    suggestion="Use `except Exception:` or a more specific class.",
                )
            )
    return out


_PRINT_NAMES: set[str] = {"print"}


def _check_print_debug(rel_path: str, tree: ast.AST, source: str) -> list[Finding]:
    """Top-level / function-body `print(...)` calls are usually leftover
    debug statements. Skip when the file is a script entry point or an
    explicit CLI module - heuristic: presence of `if __name__` guard."""
    if "if __name__" in source:
        return []
    out: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _PRINT_NAMES:
                out.append(
                    Finding(
                        rule_id="print-debug",
                        severity="info",
                        category="quality",
                        message="`print(...)` looks like leftover debug output.",
                        file=rel_path,
                        line=node.lineno,
                        suggestion="Use `logging.info(...)` or remove before merge.",
                    )
                )
    return out


_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b(?P<rest>[^\n]*)", re.IGNORECASE)
_TICKET_RE = re.compile(r"(?:#|[A-Z]{2,}-)\d+")


def _check_todo_no_ticket(rel_path: str, source: str) -> list[Finding]:
    """A TODO/FIXME without a ticket reference (#123 or ABC-123) tends to
    rot. Prefer linking to an issue tracker."""
    out: list[Finding] = []
    for i, line in enumerate(source.splitlines(), start=1):
        m = _TODO_RE.search(line)
        if m is None:
            continue
        rest = m.group("rest") or ""
        if _TICKET_RE.search(rest):
            continue
        out.append(
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
    return out


def _check_pass_only_function(rel_path: str, tree: ast.AST) -> list[Finding]:
    """A function whose entire body is `pass` is almost always either
    a stub left by a refactor or AI-generated boilerplate that wasn't
    finished. Flag as ai-pattern, low severity."""
    out: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Methods inside Protocol / abstract bases are intentionally pass.
            # We can't tell from the AST alone (would need to inspect bases),
            # so we keep severity at 'info' to avoid noise.
            body = node.body
            non_doc = [
                n
                for n in body
                if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
            ]
            if len(non_doc) == 1 and isinstance(non_doc[0], ast.Pass):
                out.append(
                    Finding(
                        rule_id="empty-function-body",
                        severity="info",
                        category="ai-pattern",
                        message=(
                            f"`{node.name}` has an empty body (only `pass`); "
                            "may be a stub or incomplete generation."
                        ),
                        file=rel_path,
                        line=node.lineno,
                    )
                )
    return out


def _check_mutable_default_arg(rel_path: str, tree: ast.AST) -> list[Finding]:
    """Mutable default arguments (`def f(x=[])`) share state across calls.

    The default is evaluated once at function-definition time, so each
    call mutates the same list/dict/set. Almost always a bug.
    """
    out: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for default in node.args.defaults:
            if isinstance(default, ast.List | ast.Dict | ast.Set):
                out.append(
                    Finding(
                        rule_id="mutable-default-arg",
                        severity="warning",
                        category="quality",
                        message=(
                            f"`{node.name}` has a mutable default argument; "
                            "it is shared across calls."
                        ),
                        file=rel_path,
                        line=node.lineno,
                        suggestion=(
                            "Use a sentinel default and create the mutable "
                            "value inside the function body, e.g. "
                            "`def f(x=None):\n    x = x or []`."
                        ),
                    )
                )
    return out


def _check_broad_except(rel_path: str, tree: ast.AST) -> list[Finding]:
    """`except Exception:` is broader than most code needs and can hide bugs.

    Less severe than bare-except (it does not catch KeyboardInterrupt),
    but still surfaces as info so reviewers can ask whether a narrower
    type fits.
    """
    out: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if isinstance(node.type, ast.Name) and node.type.id == "Exception":
            out.append(
                Finding(
                    rule_id="broad-except",
                    severity="info",
                    category="quality",
                    message=(
                        "`except Exception:` catches almost everything; "
                        "consider a narrower exception type."
                    ),
                    file=rel_path,
                    line=node.lineno,
                )
            )
    return out


def _check_assert_in_prod_code(rel_path: str, tree: ast.AST) -> list[Finding]:
    """`assert` statements are stripped by Python's `-O` flag.

    Using assert for security checks or runtime invariants in production
    code is a known footgun. Tests are exempt.
    """
    if "/tests/" in rel_path or "/test_" in rel_path or rel_path.startswith("tests/"):
        return []
    out: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            out.append(
                Finding(
                    rule_id="assert-in-prod",
                    severity="warning",
                    category="security",
                    message=(
                        "`assert` is stripped under `python -O`. "
                        "Do not use it for security or runtime checks."
                    ),
                    file=rel_path,
                    line=node.lineno,
                    suggestion=(
                        "Raise an explicit exception instead "
                        "(e.g. `if not x: raise ValueError(...)`)."
                    ),
                )
            )
    return out


_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # AWS access key (very high precision)
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key"),
    # GitHub fine-grained token
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}"), "GitHub personal access token"),
    (re.compile(r"\bghs_[A-Za-z0-9]{30,}"), "GitHub installation token"),
    # OpenAI key
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "OpenAI-style API key"),
    # Anthropic key
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic API key"),
    # Slack bot token
    (re.compile(r"\bxoxb-[A-Za-z0-9-]{10,}"), "Slack bot token"),
    # Inline password literal (best-effort; we only flag when written
    # like `password = "..."` so we keep precision reasonable)
    (
        re.compile(
            r"(?:password|passwd|secret|api[_-]?key|token)\s*=\s*"
            r'["\'](?P<val>[A-Za-z0-9!@#$%^&*_\-+=]{8,})["\']\s*$',
            re.IGNORECASE | re.MULTILINE,
        ),
        "hardcoded credential literal",
    ),
]


def _check_hardcoded_secret(rel_path: str, source: str) -> list[Finding]:
    """Surface obvious hardcoded credentials. Critical severity.

    Scans the raw source (not the AST) because secrets can appear in
    string literals across many shapes. Patterns are deliberately
    high-precision so we don't cry wolf.
    """
    out: list[Finding] = []
    for pattern, label in _SECRET_PATTERNS:
        for m in pattern.finditer(source):
            line = source.count("\n", 0, m.start()) + 1
            out.append(
                Finding(
                    rule_id="hardcoded-secret",
                    severity="critical",
                    category="security",
                    message=(
                        f"Possible hardcoded secret: {label}. "
                        "Move secrets to environment variables or a vault."
                    ),
                    file=rel_path,
                    line=line,
                )
            )
    return out


# ---------------------------------------------------------------------------
# PR-level rules
# ---------------------------------------------------------------------------


_MIN_PR_DESCRIPTION_CHARS = 30


def check_pr_metadata(pr_title: str | None, pr_description: str | None) -> list[Finding]:
    """Run rules that operate on the PR's own metadata, not its files."""
    out: list[Finding] = []

    if pr_title is not None:
        title = pr_title.strip()
        if title.lower() in {"wip", "draft", "tmp", "test", ""} or len(title) < 10:
            out.append(
                Finding(
                    rule_id="pr-title-uninformative",
                    severity="warning",
                    category="commit",
                    message=(
                        "PR title is too short or non-descriptive. Reviewers "
                        "scan titles in lists - the title should explain WHAT changed."
                    ),
                    suggestion=(
                        "Use a concise imperative-mood title, e.g. "
                        "'Add transitive-import affecting to sts'."
                    ),
                )
            )

    if pr_description is not None:
        desc = pr_description.strip()
        if len(desc) < _MIN_PR_DESCRIPTION_CHARS:
            out.append(
                Finding(
                    rule_id="pr-description-too-short",
                    severity="info",
                    category="commit",
                    message=(
                        f"PR description is under {_MIN_PR_DESCRIPTION_CHARS} characters. "
                        "Future maintainers (and you in 6 months) will thank a fuller description."
                    ),
                    suggestion=("Cover: what changed, why, and how to verify."),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Top-level dispatcher
# ---------------------------------------------------------------------------


def check_file(repo_root: Path, rel_path: str) -> list[Finding]:
    """Run the right rule pack(s) for one file.

    v0.0.1: Python only. v0.0.2 adds JS / TS via the rules_js module
    (which depends on tree-sitter; gracefully no-ops if unavailable).
    """
    if rel_path.endswith(".py"):
        full = repo_root / rel_path
        try:
            source = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return check_python_file(rel_path, source)
    if rel_path.endswith((".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")):
        # Lazy import keeps tree-sitter loading off the hot path for
        # all-Python repos.
        from apr import rules_js

        return rules_js.check_file(repo_root, rel_path)
    return []
