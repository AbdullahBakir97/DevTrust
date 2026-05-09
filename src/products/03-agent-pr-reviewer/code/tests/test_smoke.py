"""Smoke + unit tests for apr v0.0.1.

Coverage:
  - rules.check_python_file: bare-except, print-debug, todo-no-ticket,
    empty function body, syntax error.
  - rules.check_pr_metadata: short title, short description.
  - engine.review: assembles findings, sorts stably, computes stats.
  - output.write_json / write_markdown: artifact shape, content.
  - cli: version, review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apr import __version__
from apr.cli import app
from apr.engine import review as review_engine
from apr.models import SCHEMA_VERSION
from apr.rules import check_pr_metadata, check_python_file
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# rules: python source
# ---------------------------------------------------------------------------


def test_bare_except_emits_warning() -> None:
    src = "def boom():\n    try:\n        pass\n    except:\n        return None\n"
    findings = check_python_file("x.py", src)
    rule_ids = {f.rule_id for f in findings}
    assert "bare-except" in rule_ids
    bare = next(f for f in findings if f.rule_id == "bare-except")
    assert bare.severity == "warning"
    assert bare.line == 4


def test_todo_with_ticket_is_silent() -> None:
    src = "# TODO #42: track this\n"
    findings = check_python_file("x.py", src)
    assert not any(f.rule_id == "todo-no-ticket" for f in findings)


def test_todo_without_ticket_is_flagged() -> None:
    src = "# TODO: clean this up later\n"
    findings = check_python_file("x.py", src)
    rule_ids = {f.rule_id for f in findings}
    assert "todo-no-ticket" in rule_ids


def test_empty_function_body_is_ai_pattern() -> None:
    src = "def stub():\n    pass\n"
    findings = check_python_file("x.py", src)
    rule_ids = {f.rule_id for f in findings}
    assert "empty-function-body" in rule_ids
    f = next(x for x in findings if x.rule_id == "empty-function-body")
    assert f.category == "ai-pattern"


def test_print_debug_skipped_in_main_guard_files() -> None:
    """Files with `if __name__ == '__main__':` are CLI-style; print there
    is intentional. Skip the debug-print rule for them."""
    src = "def f() -> None:\n    print('hi')\n\nif __name__ == '__main__':\n    f()\n"
    findings = check_python_file("cli_like.py", src)
    assert not any(f.rule_id == "print-debug" for f in findings)


def test_syntax_error_is_flagged() -> None:
    src = "def oh no(:\n"
    findings = check_python_file("broken.py", src)
    assert any(f.rule_id == "syntax-error" for f in findings)


# ---------------------------------------------------------------------------
# rules: PR metadata
# ---------------------------------------------------------------------------


def test_pr_title_short_flagged() -> None:
    findings = check_pr_metadata("WIP", "long description over thirty chars long here")
    rule_ids = {f.rule_id for f in findings}
    assert "pr-title-uninformative" in rule_ids


def test_pr_description_short_flagged() -> None:
    findings = check_pr_metadata("Add a fully descriptive title", "short")
    rule_ids = {f.rule_id for f in findings}
    assert "pr-description-too-short" in rule_ids


def test_pr_metadata_silent_when_good() -> None:
    findings = check_pr_metadata(
        "Add transitive-import affecting to sts",
        "Wires sts.selector through repox v0.3 imports for deeper test selection.",
    )
    assert findings == []


# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------


def test_review_engine_assembles_findings(py_repo: Path) -> None:
    report = review_engine(
        py_repo,
        ["bare_except.py", "todo_no_ticket.py", "good.py"],
        pr_title="Refactor error handling",
        pr_description="Tighten the bare except in boom() and link the TODOs.",
    )
    assert report.schema_version == SCHEMA_VERSION
    rule_ids = {f.rule_id for f in report.findings}
    assert "bare-except" in rule_ids
    assert "todo-no-ticket" in rule_ids
    # Stats tally up correctly
    s = report.stats
    assert s.total == sum([s.info, s.warning, s.error, s.critical])


def test_review_engine_findings_are_stably_sorted(py_repo: Path) -> None:
    """Re-running the engine on the same inputs produces the same order."""
    r1 = review_engine(py_repo, ["bare_except.py", "todo_no_ticket.py", "debug_print.py"])
    r2 = review_engine(py_repo, ["bare_except.py", "todo_no_ticket.py", "debug_print.py"])
    assert [f.rule_id for f in r1.findings] == [f.rule_id for f in r2.findings]
    assert [(f.file, f.line) for f in r1.findings] == [(f.file, f.line) for f in r2.findings]


def test_review_engine_empty_when_clean(py_repo: Path) -> None:
    report = review_engine(py_repo, ["good.py"])
    assert report.findings == []
    assert report.stats.total == 0


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


def test_cli_review_writes_artifacts(py_repo: Path) -> None:
    result = runner.invoke(
        app,
        [
            "review",
            "--repo",
            str(py_repo),
            "--changed",
            "bare_except.py",
            "--title",
            "Refactor error handling",
            "--description",
            "Tighten the bare except handler in boom().",
        ],
    )
    assert result.exit_code == 0
    json_path = py_repo / ".apr" / "review.json"
    md_path = py_repo / ".apr" / "review.md"
    assert json_path.is_file()
    assert md_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.0.1"
    assert data["tool_version"] == __version__
    assert any(f["rule_id"] == "bare-except" for f in data["findings"])


def test_cli_review_quiet_is_quiet(py_repo: Path) -> None:
    result = runner.invoke(
        app,
        [
            "review",
            "--repo",
            str(py_repo),
            "--changed",
            "good.py",
            "--quiet",
        ],
    )
    assert result.exit_code == 0
    assert "Reviewing" not in result.stdout


# ---------------------------------------------------------------------------
# v0.0.2: additional Python rules
# ---------------------------------------------------------------------------


def test_mutable_default_arg_flagged() -> None:
    src = "def f(x=[], y={}, z=set()):\n    return x\n"
    findings = check_python_file("x.py", src)
    rule_ids = [f.rule_id for f in findings if f.rule_id == "mutable-default-arg"]
    # We flag list and dict defaults; set() is a Call, not a literal -- skipped.
    assert len(rule_ids) >= 2


def test_broad_except_flagged() -> None:
    src = "def f():\n    try:\n        return 1 / 0\n    except Exception:\n        return -1\n"
    findings = check_python_file("x.py", src)
    assert any(f.rule_id == "broad-except" for f in findings)


def test_assert_in_prod_code_flagged() -> None:
    src = "def f(x):\n    assert x > 0\n    return x\n"
    findings = check_python_file("src/lib.py", src)
    assert any(f.rule_id == "assert-in-prod" for f in findings)


def test_assert_in_test_code_silent() -> None:
    src = "def test_x():\n    assert 1 + 1 == 2\n"
    findings = check_python_file("tests/test_x.py", src)
    assert not any(f.rule_id == "assert-in-prod" for f in findings)


def test_hardcoded_secret_aws_key(py_secret_repo: Path) -> None:
    from apr.rules import check_file

    findings = check_file(py_secret_repo, "leak.py")
    secret_findings = [f for f in findings if f.rule_id == "hardcoded-secret"]
    assert len(secret_findings) == 1
    assert secret_findings[0].severity == "critical"


def test_hardcoded_secret_clean_file_silent(py_secret_repo: Path) -> None:
    from apr.rules import check_file

    findings = check_file(py_secret_repo, "clean.py")
    assert not any(f.rule_id == "hardcoded-secret" for f in findings)


# ---------------------------------------------------------------------------
# v0.0.2: JS/TS rule pack via tree-sitter
# ---------------------------------------------------------------------------


def test_js_console_log_flagged(js_repo: Path) -> None:
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from apr.rules import check_file

    findings = check_file(js_repo, "console_log.ts")
    assert any(f.rule_id == "console-log" for f in findings)


def test_js_console_log_skipped_in_entry_file(js_repo: Path) -> None:
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from apr.rules import check_file

    findings = check_file(js_repo, "cli.js")
    assert not any(f.rule_id == "console-log" for f in findings)


def test_js_debugger_statement_flagged(js_repo: Path) -> None:
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from apr.rules import check_file

    findings = check_file(js_repo, "debugger_stmt.ts")
    assert any(f.rule_id == "debugger-statement" for f in findings)


def test_js_var_declaration_flagged(js_repo: Path) -> None:
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from apr.rules import check_file

    findings = check_file(js_repo, "var_decl.js")
    assert any(f.rule_id == "var-declaration" for f in findings)


def test_js_todo_no_ticket_flagged(js_repo: Path) -> None:
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from apr.rules import check_file

    findings = check_file(js_repo, "todo_no_ticket.ts")
    no_ticket = [f for f in findings if f.rule_id == "todo-no-ticket"]
    # Two TODOs in the file; only the one without #42 should fire.
    assert len(no_ticket) == 1


def test_js_clean_file_no_findings(js_repo: Path) -> None:
    pytest = __import__("pytest")
    pytest.importorskip("tree_sitter")
    pytest.importorskip("tree_sitter_language_pack")

    from apr.rules import check_file

    findings = check_file(js_repo, "good.ts")
    assert findings == []


def test_unsupported_extension_returns_empty(tmp_path: Path) -> None:
    """A `.rs` or `.go` file gets [] until we ship those rule packs."""
    from apr.rules import check_file

    (tmp_path / "x.rs").write_text("fn main() {}\n", encoding="utf-8")
    findings = check_file(tmp_path, "x.rs")
    assert findings == []


def test_hardcoded_secret_fires_even_on_unparseable_file() -> None:
    """A syntax error must NOT silence source-text rules like
    hardcoded-secret. Regression test for the bug where the demo
    `Out-File`-encoded file showed only `syntax-error` and missed
    the embedded AKIA-shaped key."""
    src = "this is not valid python = ::: AWS_KEY = " + '"AKIA' + "X" * 16 + '"\n'
    findings = check_python_file("broken.py", src)
    rule_ids = {f.rule_id for f in findings}
    # Both must fire: the syntax error AND the hardcoded-secret check.
    assert "syntax-error" in rule_ids
    assert "hardcoded-secret" in rule_ids


def test_todo_fires_even_on_unparseable_file() -> None:
    """todo-no-ticket should also survive a broken parse."""
    src = "garbage code # TODO: track this somewhere\n???\n"
    findings = check_python_file("broken.py", src)
    rule_ids = {f.rule_id for f in findings}
    assert "syntax-error" in rule_ids
    assert "todo-no-ticket" in rule_ids


# ---------------------------------------------------------------------------
# v0.1.0: AI rule pack (hallucinated-symbol + diff-comprehension stub)
# ---------------------------------------------------------------------------


def _write_repox_artifact(
    repo_root: Path,
    *,
    edges: list[dict[str, object]],
    imports: list[dict[str, object]] | None = None,
) -> None:
    """Write a minimal architecture.json that apr.repox_integration accepts."""
    repox_dir = repo_root / ".repox"
    repox_dir.mkdir(exist_ok=True)
    arch = {
        "schema_version": "0.3.0",
        "tool_version": "0.3.0",
        "files": [{"path": "x.py", "language": "Python", "size_bytes": 1, "is_binary": False}],
        "call_graph": {
            "imports": imports or [],
            "symbols": [],
            "edges": edges,
        },
    }
    (repox_dir / "architecture.json").write_text(json.dumps(arch), encoding="utf-8")


def test_ai_rule_hallucinated_symbol_fires_for_unresolved_callee(
    tmp_path: Path,
) -> None:
    """An edge with target_file=None whose callee isn't a known name AND
    isn't imported should be flagged."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "x.py",
                "caller": "do_thing",
                "callee_name": "make_widget",  # NOT a builtin, NOT imported
                "target_file": None,
                "line": 5,
            },
        ],
    )
    (tmp_path / "x.py").write_text("def do_thing(): pass\n", encoding="utf-8")

    report = review_engine(tmp_path, ["x.py"], enable_ai=True)
    rule_ids = {f.rule_id for f in report.findings}
    assert "ai-review:hallucinated-symbol" in rule_ids


def test_ai_rule_silences_known_builtins_and_imports(tmp_path: Path) -> None:
    """Builtins like `len`, `print` and properly-imported names should NOT fire."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "x.py",
                "caller": "f",
                "callee_name": "len",  # builtin
                "target_file": None,
                "line": 1,
            },
            {
                "source_file": "x.py",
                "caller": "f",
                "callee_name": "json.dumps",  # stdlib root
                "target_file": None,
                "line": 2,
            },
            {
                "source_file": "x.py",
                "caller": "f",
                "callee_name": "helper",  # imported -> safe
                "target_file": None,
                "line": 3,
            },
        ],
        imports=[
            {
                "source_file": "x.py",
                "target_module": "lib.helper",
                "target_file": "lib.py",
                "is_relative": False,
                "line": 1,
            },
        ],
    )
    (tmp_path / "x.py").write_text("def f(): pass\n", encoding="utf-8")

    report = review_engine(tmp_path, ["x.py"], enable_ai=True)
    rule_ids = [f.rule_id for f in report.findings]
    assert "ai-review:hallucinated-symbol" not in rule_ids


def test_ai_rule_only_flags_changed_files(tmp_path: Path) -> None:
    """Edges in OTHER files don't fire just because their callee is unresolved.
    Reviewers care about what THIS PR touched."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "untouched.py",  # NOT in changed_files
                "caller": "z",
                "callee_name": "inventedThing",
                "target_file": None,
                "line": 5,
            },
        ],
    )

    report = review_engine(tmp_path, ["something_else.py"], enable_ai=True)
    rule_ids = [f.rule_id for f in report.findings]
    assert "ai-review:hallucinated-symbol" not in rule_ids


def test_ai_rules_off_by_default(tmp_path: Path) -> None:
    """Without --enable-ai, the AI rule pack should not run even if the
    artifact is present."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "x.py",
                "caller": "f",
                "callee_name": "definitelyHallucinated",
                "target_file": None,
                "line": 1,
            },
        ],
    )
    (tmp_path / "x.py").write_text("def f(): pass\n", encoding="utf-8")

    report = review_engine(tmp_path, ["x.py"])  # enable_ai=False (default)
    rule_ids = [f.rule_id for f in report.findings]
    assert "ai-review:hallucinated-symbol" not in rule_ids


def test_diff_comprehension_uses_provider_and_namespaces_findings(
    tmp_path: Path,
) -> None:
    """Findings from the LLMProvider are re-emitted under our rule_id namespace."""
    from apr.engine import review as review_engine
    from apr.models import Finding

    class CannedProvider:
        name = "canned"

        def analyze_diff(
            self,
            diff: str,
            pr_title: str | None,
            pr_description: str | None,
        ) -> list[Finding]:
            return [
                Finding(
                    rule_id="vendor-internal:foo",
                    severity="warning",
                    category="ai-pattern",
                    message="The PR description doesn't mention the API change.",
                    file=None,
                )
            ]

    report = review_engine(
        tmp_path,
        [],
        pr_title="Add feature",
        pr_description="Adds the foo widget.",
        enable_ai=True,
        llm_provider=CannedProvider(),
        diff="diff --git a/x.py b/x.py\n",
    )
    rule_ids = [f.rule_id for f in report.findings]
    assert "ai-review:diff-comprehension" in rule_ids
    # Vendor-internal IDs MUST NOT leak into the public report.
    assert not any(rid.startswith("vendor-internal") for rid in rule_ids)


def test_diff_comprehension_silent_when_provider_raises() -> None:
    """A misconfigured / failing provider must not break review."""
    from apr.rules_ai import _check_diff_comprehension

    class BoomProvider:
        name = "boom"

        def analyze_diff(
            self,
            diff: str,
            pr_title: str | None,
            pr_description: str | None,
        ) -> list:
            raise RuntimeError("api error")

    findings = _check_diff_comprehension(BoomProvider(), "diff", "title", "desc")
    assert findings == []


def test_anthropic_provider_stub_raises_not_implemented() -> None:
    """The v0.1.0 AnthropicProvider intentionally raises NotImplementedError
    so the engine's exception-shield kicks in. Real impl is v0.1.1."""
    pytest = __import__("pytest")
    pytest.importorskip("anthropic")  # if the wheel isn't here, skip

    from apr.llm import AnthropicProvider

    p = AnthropicProvider(api_key="sk-fake")
    with pytest.raises(NotImplementedError):
        p.analyze_diff("diff", "title", "desc")


def test_repox_integration_returns_none_for_missing_artifact(tmp_path: Path) -> None:
    from apr.repox_integration import load

    assert load(tmp_path) is None


def test_repox_integration_returns_none_when_no_call_graph(tmp_path: Path) -> None:
    """A repox v0.0.x / v0.1.x artifact (no call_graph) yields None."""
    from apr.repox_integration import load

    repox_dir = tmp_path / ".repox"
    repox_dir.mkdir()
    (repox_dir / "architecture.json").write_text(
        json.dumps({"schema_version": "0.1.0", "files": []}), encoding="utf-8"
    )
    assert load(tmp_path) is None


# ---------------------------------------------------------------------------
# v0.1.1: AnthropicProvider real implementation + prompts module
# ---------------------------------------------------------------------------


def test_prompts_build_includes_title_description_and_diff() -> None:
    """The prompt template surfaces all three inputs verbatim."""
    from apr.prompts import build_prompt

    out = build_prompt(
        diff="diff --git a/x.py b/x.py\n+new line",
        pr_title="Add transitive-import affecting",
        pr_description="Wires sts.selector through repox.",
    )
    assert "Add transitive-import affecting" in out
    assert "Wires sts.selector through repox" in out
    assert "diff --git a/x.py" in out
    assert "+new line" in out


def test_prompts_build_truncates_long_diffs() -> None:
    """A huge diff is bounded; the truncation marker explains why."""
    from apr.prompts import build_prompt

    long_diff = "diff line\n" * 20_000  # well above default cap
    out = build_prompt(
        diff=long_diff,
        pr_title="t",
        pr_description="d",
        max_diff_chars=1000,
    )
    assert "diff truncated from" in out
    assert len(out) < 5000  # everything bounded


def test_prompts_parse_strict_json() -> None:
    """The happy path: model returns clean JSON we can parse directly."""
    from apr.prompts import parse_response

    text = '{"findings":[{"severity":"warning","message":"PR claims X but diff does not show X.","file":"src/foo.py","line":3}]}'
    findings = parse_response(text)
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "ai-review:diff-comprehension"
    assert f.severity == "warning"
    assert f.file == "src/foo.py"
    assert f.line == 3


def test_prompts_parse_extracts_json_from_prose_wrapper() -> None:
    """If the model wraps JSON in 'Here you go: { ... }', we still recover."""
    from apr.prompts import parse_response

    text = (
        "Here are the findings:\n"
        '{"findings":[{"severity":"info","message":"All looks consistent."}]}\n'
        "Hope this helps!"
    )
    findings = parse_response(text)
    assert len(findings) == 1
    assert findings[0].severity == "info"
    assert findings[0].file is None
    assert findings[0].line is None


def test_prompts_parse_returns_empty_on_garbage() -> None:
    """Unparseable replies must return [] rather than crash."""
    from apr.prompts import parse_response

    assert parse_response("not even close to JSON") == []
    assert parse_response("") == []
    assert parse_response('{"wrong":"shape"}') == []


def test_prompts_parse_skips_invalid_severity() -> None:
    """A finding with an invalid severity ('catastrophic') is dropped, not raised."""
    from apr.prompts import parse_response

    text = (
        '{"findings":['
        '{"severity":"catastrophic","message":"x"},'
        '{"severity":"warning","message":"valid one","file":"y.py","line":1}'
        "]}"
    )
    findings = parse_response(text)
    assert len(findings) == 1
    assert findings[0].severity == "warning"


def test_anthropic_provider_uses_injected_client_and_returns_findings() -> None:
    """With a mocked client that returns a JSON-shaped Message, the
    provider returns properly-namespaced Findings."""
    pytest = __import__("pytest")
    pytest.importorskip("anthropic")

    from apr.llm import AnthropicProvider

    class _FakeBlock:
        def __init__(self, text: str) -> None:
            self.type = "text"
            self.text = text

    class _FakeMessage:
        def __init__(self, text: str) -> None:
            self.content = [_FakeBlock(text)]

    class _FakeMessages:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def create(self, **kwargs: Any) -> _FakeMessage:
            self.calls.append(kwargs)
            return _FakeMessage(
                '{"findings":['
                '{"severity":"warning","message":"PR description omits the schema bump.","file":"src/m.py","line":12}'
                "]}"
            )

    class _FakeClient:
        def __init__(self) -> None:
            self.messages = _FakeMessages()

    fake = _FakeClient()
    provider = AnthropicProvider(api_key="sk-fake", client=fake)
    findings = provider.analyze_diff(
        "diff --git a/src/m.py b/src/m.py\n+SCHEMA = '0.2'",
        "Refactor models",
        "Tighten validation.",
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "ai-review:diff-comprehension"
    assert findings[0].severity == "warning"
    assert findings[0].file == "src/m.py"
    assert findings[0].line == 12
    # Confirm the SDK call was made with the right knobs
    call = fake.messages.calls[0]
    assert call["model"]
    assert call["max_tokens"] >= 256
    assert "system" in call
    assert call["messages"][0]["role"] == "user"


def test_anthropic_provider_returns_empty_on_sdk_exception() -> None:
    """Rate limits / network errors must reduce to 'no findings' silently."""
    pytest = __import__("pytest")
    pytest.importorskip("anthropic")

    from apr.llm import AnthropicProvider

    class _BoomMessages:
        def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("rate limited")

    class _BoomClient:
        messages = _BoomMessages()

    provider = AnthropicProvider(api_key="sk-fake", client=_BoomClient())
    findings = provider.analyze_diff("diff", "title", "desc")
    assert findings == []


def test_anthropic_provider_returns_empty_on_unparseable_reply() -> None:
    """The model breaks our JSON contract -> no findings, no crash."""
    pytest = __import__("pytest")
    pytest.importorskip("anthropic")

    from apr.llm import AnthropicProvider

    class _Block:
        type = "text"
        text = "I'm not feeling JSON today."

    class _Msg:
        def __init__(self) -> None:
            self.content = [_Block()]

    class _Messages:
        def create(self, **kwargs: Any) -> Any:
            return _Msg()

    class _Client:
        messages = _Messages()

    provider = AnthropicProvider(api_key="sk-fake", client=_Client())
    findings = provider.analyze_diff("diff", "title", "desc")
    assert findings == []


def test_apr_version_is_semver_shaped() -> None:
    """Structural check: __version__ is a SemVer triple. Survives bumps
    without edits -- avoids the stale-pin pattern release.py guards
    against. Same shape used in agtrace, tokencost, whychanged."""
    import re

    from apr import __version__

    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-+].+)?", __version__), __version__


# ---------------------------------------------------------------------------
# v0.2.0: ai-review:hallucinated-symbol extended to JS / TS
# ---------------------------------------------------------------------------


def test_ai_rule_js_hallucinated_callee_flagged(tmp_path: Path) -> None:
    """A JS edge whose callee is neither in the JS allowlist nor in the
    file's imports gets flagged."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "src/widget.ts",
                "caller": "renderWidget",
                "callee_name": "computeMagicSauce",  # invented
                "target_file": None,
                "line": 7,
            },
        ],
    )
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "widget.ts").write_text(
        "export function renderWidget(): void {}\n", encoding="utf-8"
    )

    report = review_engine(tmp_path, ["src/widget.ts"], enable_ai=True)
    flagged = [f for f in report.findings if f.rule_id == "ai-review:hallucinated-symbol"]
    assert len(flagged) == 1
    assert flagged[0].file == "src/widget.ts"
    assert flagged[0].line == 7
    assert "computeMagicSauce" in flagged[0].message


def test_ai_rule_js_console_log_safe(tmp_path: Path) -> None:
    """`console.log` is a JS browser/node global -- must not fire."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "x.js",
                "caller": "log",
                "callee_name": "console.log",
                "target_file": None,
                "line": 2,
            },
            {
                "source_file": "x.js",
                "caller": "warn",
                "callee_name": "console.error",
                "target_file": None,
                "line": 3,
            },
        ],
    )
    (tmp_path / "x.js").write_text("function log() {}\n", encoding="utf-8")

    report = review_engine(tmp_path, ["x.js"], enable_ai=True)
    assert not any(f.rule_id == "ai-review:hallucinated-symbol" for f in report.findings)


def test_ai_rule_js_browser_globals_safe(tmp_path: Path) -> None:
    """document, fetch, localStorage etc. are recognized browser globals."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "ui.tsx",
                "caller": "App",
                "callee_name": "document.querySelector",
                "target_file": None,
                "line": 5,
            },
            {
                "source_file": "ui.tsx",
                "caller": "App",
                "callee_name": "fetch",
                "target_file": None,
                "line": 6,
            },
            {
                "source_file": "ui.tsx",
                "caller": "App",
                "callee_name": "localStorage.getItem",
                "target_file": None,
                "line": 7,
            },
        ],
    )
    (tmp_path / "ui.tsx").write_text("export function App() { return null; }\n", encoding="utf-8")

    report = review_engine(tmp_path, ["ui.tsx"], enable_ai=True)
    assert not any(f.rule_id == "ai-review:hallucinated-symbol" for f in report.findings)


def test_ai_rule_js_node_globals_safe(tmp_path: Path) -> None:
    """process.* and Buffer.* are Node.js globals."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "server.ts",
                "caller": "boot",
                "callee_name": "process.exit",
                "target_file": None,
                "line": 1,
            },
            {
                "source_file": "server.ts",
                "caller": "boot",
                "callee_name": "Buffer.from",
                "target_file": None,
                "line": 2,
            },
        ],
    )
    (tmp_path / "server.ts").write_text("export function boot() {}\n", encoding="utf-8")

    report = review_engine(tmp_path, ["server.ts"], enable_ai=True)
    assert not any(f.rule_id == "ai-review:hallucinated-symbol" for f in report.findings)


def test_ai_rule_js_npm_root_safe_via_imports(tmp_path: Path) -> None:
    """Imported npm-package binding is silenced via imports_by_source.

    `import express from 'express'` -> the binding hint is 'express',
    matching the JS allowlist so the call passes either way. We model
    the same flow here through imports_by_source to confirm the path
    works end-to-end.
    """
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "server.ts",
                "caller": "boot",
                "callee_name": "express",
                "target_file": None,
                "line": 3,
            },
        ],
        imports=[
            {
                "source_file": "server.ts",
                "target_module": "express",
                "target_file": None,
                "is_relative": False,
                "line": 1,
            },
        ],
    )
    (tmp_path / "server.ts").write_text("export function boot() {}\n", encoding="utf-8")

    report = review_engine(tmp_path, ["server.ts"], enable_ai=True)
    assert not any(f.rule_id == "ai-review:hallucinated-symbol" for f in report.findings)


def test_ai_rule_ts_in_repo_call_resolved(tmp_path: Path) -> None:
    """Edges whose target_file is set are skipped regardless of language.
    This is what catches in-repo `import { x } from './y'` calls in JS/TS
    after repox v0.4 resolves them on the call edge itself."""
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "src/widget.ts",
                "caller": "renderWidget",
                "callee_name": "helperFromOtherFile",
                "target_file": "src/helpers.ts",  # resolved in-repo
                "line": 5,
            },
        ],
    )
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "widget.ts").write_text(
        "export function renderWidget() {}\n", encoding="utf-8"
    )

    report = review_engine(tmp_path, ["src/widget.ts"], enable_ai=True)
    assert not any(f.rule_id == "ai-review:hallucinated-symbol" for f in report.findings)


def test_ai_rule_js_wrong_language_callee_flagged(tmp_path: Path) -> None:
    """A JS file calling `pathlib.Path(...)` is wrong-language — must flag.

    The Python allowlist (which contains 'pathlib') is NOT consulted
    when the source file is `.js`/`.ts`. Catches the AI-hallucination
    shape where the model mixes Python stdlib calls into JS code.
    `pathlib` chosen over `os` because the rule silences first segments
    of length <= 2 (intended to suppress single-letter loop variables).
    """
    from apr.engine import review as review_engine

    _write_repox_artifact(
        tmp_path,
        edges=[
            {
                "source_file": "weird.ts",
                "caller": "f",
                "callee_name": "pathlib.Path",
                "target_file": None,
                "line": 1,
            },
        ],
    )
    (tmp_path / "weird.ts").write_text("export function f() {}\n", encoding="utf-8")

    report = review_engine(tmp_path, ["weird.ts"], enable_ai=True)
    flagged = [f for f in report.findings if f.rule_id == "ai-review:hallucinated-symbol"]
    assert len(flagged) == 1
    assert "pathlib.Path" in flagged[0].message


def test_binding_hint_for_js_specifiers() -> None:
    """Unit-level coverage for the language-aware binding extractor."""
    from apr.repox_integration import _binding_hint

    # JS bare package
    assert _binding_hint("react") == "react"
    assert _binding_hint("react-dom") == "react-dom"
    # JS subpath -> last slash segment
    assert _binding_hint("react-dom/client") == "client"
    # JS scoped package
    assert _binding_hint("@scope/pkg") == "pkg"
    assert _binding_hint("@scope/pkg/sub") == "sub"
    # JS relative -> None (in-repo path; rule short-circuits via target_file)
    assert _binding_hint("./helpers") is None
    assert _binding_hint("../shared") is None
    assert _binding_hint(".") is None
    # Python bare module
    assert _binding_hint("os") == "os"
    # Python dotted -> last segment
    assert _binding_hint("os.path") == "path"
    assert _binding_hint("a.b.c") == "c"
    # Empty / whitespace
    assert _binding_hint("") is None
    assert _binding_hint("   ") is None
