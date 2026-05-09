# Agent-PR Reviewer — changelog

All notable changes to `apr` are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-05-09

### Added
- **`ai-review:hallucinated-symbol` is now multi-language.** The deterministic AI-pattern checker that flags calls to names that don't exist now consumes Repo X-ray v0.4's JavaScript / TypeScript call edges in addition to Python. The rule fires the same way for all three languages: walk the artifact's edges, scoped to changed files, and flag callees whose first segment doesn't resolve to an in-repo symbol or a known global / package root.
  - **Language-aware allowlist.** `_KNOWN_NAMES_PY` (Python builtins + stdlib + ~50 popular pip roots) and `_KNOWN_NAMES_JS` (ECMAScript globals, browser DOM globals, Node.js globals, ~70 popular npm package roots) are now disjoint. A `.ts` file calling `os.path.join` is not silenced by the Python allowlist — it's correctly flagged as a wrong-language hallucination signal.
  - **In-repo JS/TS imports already pass.** Repox v0.4 sets `target_file` on every call edge whose callee was bound via `import { x } from './y'` to an in-repo file. The rule's existing `target_file is set -> skip` short-circuit handles those without changes.
  - **External JS/TS imports.** `apr.repox_integration._binding_hint` now extracts a usable binding name from JS/TS module specifiers — `react-dom/client` → `client`, `@scope/pkg/sub` → `sub`, bare `'express'` → `'express'`. Renamed default imports (`import _ from 'lodash'`) are silenced by the existing two-character-name skip rather than misflagged.
- **8 new tests** in `tests/test_smoke.py`:
  - `test_ai_rule_js_hallucinated_callee_flagged` — truly invented JS callee fires.
  - `test_ai_rule_js_console_log_safe` — `console.log` doesn't fire.
  - `test_ai_rule_js_browser_globals_safe` — `document.querySelector`, `fetch`, `localStorage.getItem` don't fire.
  - `test_ai_rule_js_node_globals_safe` — `process.exit`, `Buffer.from` don't fire.
  - `test_ai_rule_js_npm_root_safe` — `express()` doesn't fire when imported.
  - `test_ai_rule_ts_in_repo_call_resolved` — call edge with `target_file` set is silent.
  - `test_ai_rule_js_wrong_language_callee_flagged` — JS file calling `os.path.join` IS flagged (Python allowlist is not consulted for JS files).
  - `test_binding_hint_for_js_specifiers` — direct unit test for the new `_binding_hint` helper.

### Changed
- `apr.repox_integration` extracts the new `_binding_hint(target_module)` helper instead of inline `lstrip + split`. Behavior unchanged for Python imports; JS/TS specifiers now produce more accurate hints (subpath last-segment, scoped-package last-segment).
- The version-pin smoke test (`test_apr_version_*`) now uses a structural SemVer regex check instead of an exact-string equality, matching the pattern used in agtrace, tokencost, and whychanged. This prevents the test from going stale on every minor bump and keeps `scripts/release.py --check` clean.

### Notes
- Schema unchanged (still `0.0.1` — additive: same `Finding` shape, same rule IDs, just broader coverage).
- Diff-comprehension rule is unchanged in v0.2.
- This release closes the only deferred v0.1 item: when we shipped repox v0.4 with JS/TS call edges, apr's hallucinated-symbol rule was still Python-only. v0.2.0 closes that gap and gives APR full multi-language coverage across all three Wave-1 supported languages (Python, JavaScript, TypeScript).
- Known limitation: renamed default imports like `import _ from 'lodash'` cannot be precisely tracked without extending the repox `Import` model to carry `local_names`. v0.2.0 mitigates by skipping ≤ 2-character first-segments; a future repox v0.5 + apr v0.3 will close this fully.

[0.2.0]: https://github.com/AbdullahBakir97/apr/compare/v0.1.1...v0.2.0

---

## [0.1.1] — 2026-05-08

### Added
- **Real Anthropic backend for `ai-review:diff-comprehension`.** `AnthropicProvider.analyze_diff()` is now a working implementation:
  - Calls the Messages API (non-streaming, single-turn) via the official `anthropic` SDK.
  - Builds a JSON-shaped prompt (system + user) via the new `apr.prompts` module — diff is truncated at 60,000 chars by default to bound input cost on runaway diffs.
  - Caps reply at 1024 tokens (configurable via the `AnthropicProvider` constructor).
  - Parses the model's reply tolerantly: tries strict `json.loads` first, then extracts the first balanced `{...}` block when the model wraps JSON in prose.
  - Filters invalid severity values silently rather than raising — no LLM tantrum can break review.
- New `apr.prompts` module — separates prompt construction + response parsing from the SDK so it can be unit-tested without the `anthropic` wheel installed.
- New env var `APR_ANTHROPIC_MODEL` lets operators override the default model (`claude-sonnet-4-6`) per deployment.
- 9 new tests: prompt construction, diff truncation, strict JSON parse, prose-wrapper recovery, garbage / invalid-severity rejection, end-to-end with a mocked SDK client, SDK-exception shielding, unparseable-reply handling, version assertion.

### Changed
- `AnthropicProvider.__init__` accepts an optional `client` keyword for tests + future dependency injection.
- The SDK `import anthropic` happens lazily inside `_ensure_client`, so `apr` installs without the optional `[ai]` extra.
- All findings produced through this rule emerge with `rule_id="ai-review:diff-comprehension"` regardless of what the model claimed — vendor-internal IDs cannot leak into the report.

### Notes
- Schema unchanged (still 0.0.1 — same Finding shape).
- Cost guidance: a typical 500-line PR diff produces ~3K input tokens + ~200 output tokens, i.e. < $0.005 per review at Sonnet pricing. Bound by `max_diff_chars` and `max_tokens`. Operators with high PR volume should monitor and tune.
- The rule is still gated behind `--enable-ai --ai-provider=anthropic` and requires `ANTHROPIC_API_KEY` in the environment. Default behavior (no flag) is unchanged: deterministic rules only, no API calls, no cost.

[0.1.1]: https://github.com/AbdullahBakir97/apr/compare/v0.1.0...v0.1.1

---

## [0.1.0] — 2026-05-08

### Added
- **AI rule pack (`ai-review:*`).** New `src/apr/rules_ai.py` ships two rules, both opt-in via `--enable-ai`:
  - `ai-review:hallucinated-symbol` (warning, ai-pattern) — **deterministic.** Walks Repo X-ray's `call_graph.edges` and flags function calls whose callee doesn't resolve to an in-repo symbol AND isn't a Python built-in / well-known stdlib root / file-local imported alias. Catches the classic AI-generation failure mode where a function call references a name that doesn't exist anywhere in the codebase.
  - `ai-review:diff-comprehension` (delegates to `LLMProvider`) — pluggable LLM-backed checker for "does the PR description accurately describe the diff." v0.1.0 ships the `NullProvider` (returns no findings) and an `AnthropicProvider` stub. The streaming Anthropic implementation is v0.1.1.
- **Repox integration** (`src/apr/repox_integration.py`) — best-effort loader for `.repox/architecture.json`. Returns `None` for older artifacts (v0.0.x / v0.1.x) without a call graph; the AI rule pack then no-ops cleanly.
- **LLM provider interface** (`src/apr/llm.py`) — `LLMProvider` Protocol + `NullProvider` + `AnthropicProvider` stub + `build_provider()` factory. Vendor swaps are a matter of writing a new provider class; the engine and rules don't change.
- **CLI flags** — `--enable-ai/--no-enable-ai` (default off), `--ai-provider null|anthropic`, `--diff PATH` (unified-diff file for diff-comprehension).
- **Optional `[ai]` extra** in `pyproject.toml` — `pip install apr[ai]` brings in the `anthropic` SDK.
- **9 new tests** covering: hallucinated-symbol fires correctly, builtin/import allow-list silences false positives, only changed files are scanned, AI off by default, provider exception shielding, vendor rule_id namespace isolation, the AnthropicProvider stub raising NotImplementedError, repox integration returning None for missing/old artifacts.

### Changed
- **`check_python_file` ordering fix.** Source-text rules (`todo-no-ticket`, `hardcoded-secret`) now run *before* AST parsing, so a syntax error doesn't silently suppress them. Regression tests added — was a real bug discovered when a BOM-encoded demo file produced only `syntax-error` and missed the embedded AKIA-shaped key.
- Promoted from `Development Status :: 3 - Alpha` to `Development Status :: 4 - Beta`.
- Engine `review()` gained kwargs: `enable_ai`, `llm_provider`, `diff`. Backward compatible — defaults preserve the v0.0.2 behavior.

### Notes
- Schema unchanged (still 0.0.1 — same Finding shape, additive rule IDs).
- AI rules are off by default to keep PR review fast and deterministic for the common case. Operators opt in per repo by adding `--enable-ai` to their CI invocation.
- The hallucinated-symbol allow-list is conservative: stdlib roots + ~50 common third-party roots + apr/repox/sts itself. False positives are corrected by adding the missing root, not by relaxing the rule.

[0.1.0]: https://github.com/AbdullahBakir97/apr/compare/v0.0.2...v0.1.0

---

## [0.0.2] — 2026-05-08

### Added
- **JS / TS rule pack** via tree-sitter (`src/apr/rules_js.py`):
  - `console-log` (info, quality) — leftover `console.log` / `.debug` / `.info` calls. Skipped in obvious entry files (presence of `process.argv`, `.listen(`, or `import.meta.main`).
  - `debugger-statement` (warning, quality) — `debugger;` left in code.
  - `var-declaration` (info, style) — `var x = ...` instead of `let`/`const`.
  - `todo-no-ticket` (info, todo) — TODO/FIXME/XXX/HACK without `#123` or `PROJ-123`. Mirror of the Python rule.
- **Additional Python rules** in `src/apr/rules.py`:
  - `mutable-default-arg` (warning, quality) — `def f(x=[])` shares state across calls.
  - `broad-except` (info, quality) — `except Exception:` is wider than most code needs.
  - `assert-in-prod` (warning, security) — `assert` is stripped under `python -O`. Test files (`tests/`, `test_*.py`) are exempt.
  - `hardcoded-secret` (critical, security) — high-precision regex pack catches AWS access keys (`AKIA*`), GitHub tokens (`ghp_*`, `ghs_*`), OpenAI keys (`sk-*`), Anthropic keys (`sk-ant-*`), Slack bot tokens (`xoxb-*`), and inline `password=`/`api_key=` literals.
- 13 new tests covering each rule end-to-end (some `pytest.importorskip` JS/TS rules when tree-sitter wheels aren't available on the platform).

### Changed
- `apr.rules.check_file` now dispatches by extension: `.py` -> Python rules, `.js`/`.jsx`/`.mjs`/`.cjs`/`.ts`/`.tsx` -> tree-sitter rules, others -> empty.
- Tree-sitter (`tree-sitter>=0.23` + `tree-sitter-language-pack>=0.4,<1.0`) graduated to required deps.

### Notes
- Schema unchanged (still **0.0.1**) — additive: same `Finding` shape, just more rule IDs.
- The hardcoded-secret rule is precision-tuned (high-confidence patterns only). False positives on `password = "x"` style literals are possible but accepted at info+ severity. False negatives on bespoke key formats are accepted; `apr` is meant to complement, not replace, dedicated secret scanners.

[0.0.2]: https://github.com/AbdullahBakir97/apr/compare/v0.0.1...v0.0.2

---

## [0.0.1] — 2026-05-08

### Added
- Initial scaffold: `apr` Python package with two CLI commands (`review`, `version`).
- Pydantic v2 schema (versioned 0.0.1): `Finding`, `ReviewInputs`, `ReviewStats`, `ReviewReport`.
- `rules` module — deterministic rule pack for Python:
  - `bare-except` (warning) — bare `except:` clause.
  - `print-debug` (info) — leftover `print(...)`, skipped in `__main__` guard files.
  - `todo-no-ticket` (info) — TODO/FIXME/XXX/HACK without `#123` / `PROJ-123` reference.
  - `empty-function-body` (info, ai-pattern) — function body is only `pass`.
  - `syntax-error` (error) — file does not parse.
- `rules.check_pr_metadata` — `pr-title-uninformative` (warning), `pr-description-too-short` (info).
- `engine` — orchestrator: PR-level checks first, then per-file rule packs; stably sorted findings; severity-bucket stats.
- `output` — JSON + Markdown writers emitting to `.apr/review.{json,md}`. The Markdown report includes a "Suggested fixes" block surfacing up to 10 suggestions with file:line.
- Workspace dep on `repox` (apr will use the architecture model for v0.0.2+ file-context rules).
- 16 smoke tests covering each rule, the engine, both writers, and the CLI.
- Apache-2.0 license, hatchling build, typer/rich/pydantic deps.

### Notes
- Wave 2 lead bet of the DevTrust platform. Consolidates the patterns from three earlier GitHub Apps (`ai-quality-gate`, `pr-coach`, `commit-craft`) into one engine.
- v0.0.1 is **Python only by design**. JS/TS rules in v0.0.2.
- LLM-backed checks (`ai-review:*` rule IDs) land in v0.1+ once the deterministic rule output is stable enough to grade against.

[0.0.1]: https://github.com/AbdullahBakir97/apr/releases/tag/v0.0.1
