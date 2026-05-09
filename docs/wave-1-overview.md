# Wave 1 — the AI-era development trust layer

> Three opinionated tools that answer the three questions every reviewer asks
> when an AI-assisted PR lands:
> **What changed in the architecture? · Which tests must run? · Should we trust the diff?**

DevTrust's Wave 1 isn't a static-analysis suite. The static-analysis market is saturated with linters and rule packs that catch obvious bugs. What's missing is a **codebase-aware, change-aware, AI-aware** trio of primitives that turn AI-augmented commits into reviewable, testable, and trustable units of work — without LLM dependence at the core.

## The three questions, mapped

| Question | Tool | Headline output |
|---|---|---|
| **What changed in the architecture?** | `repox` | Architecture model of the codebase: files, imports, symbols, function-call edges across Python + JavaScript + TypeScript. |
| **Which tests must run?** | `sts` | Per-test verdict (`must_run` / `should_run` / `safe_skip`) given a change set, with transitive-import awareness and framework detection (pytest, jest, vitest, gotest, cargo). |
| **Should we trust the diff?** | `apr` | Deterministic + AI-pattern review findings: hardcoded secrets, hallucinated symbols, broad-except, mutable defaults, console.log, debugger, missing TODO ticket links — across Python and JS/TS. |

Each tool stands alone. The interesting story is what happens when they're wired together.

## The integration

`apr` and `sts` both consume `repox`'s `architecture.json` for context. When `repox` ships a call-graph + import-graph at v0.4.0, `sts` instantly knows transitive impact (a change in `helpers.py` affects every test importing it, even two hops away), and `apr` instantly gets a "hallucinated symbol" rule (an LLM-introduced call to `make_widget()` that doesn't exist in the repo's call graph fires as a warning).

```
repo/
├── .repox/architecture.json      (built by `repox build .`)
│      ▲
│      │
├── .sts/selection.{json,md}      (built by `sts select` — uses architecture.json)
│
├── .apr/review.{json,md}         (built by `apr review` — uses architecture.json)
└── ...
```

**One architecture model. Three trust outputs.** No agent in the loop unless you opt in via `apr --enable-ai`.

## The canonical setup (~5 lines on every PR)

```bash
# CI step run on every PR:
repox build .                                              # 1. model the repo
sts select --repo . --diff "$(gh pr diff)" --use-repox     # 2. choose tests
apr review --repo . --title "$PR_TITLE" --description "$PR_DESC"
                                                           # 3. review the diff
pytest $(jq -r '.must_run[] | .nodeid' .sts/selection.json)
                                                           # 4. run only the necessary tests
gh pr comment "$(cat .apr/review.md .sts/selection.md)"    # 5. post sticky comment
```

Five commands. Two artifacts in the repo (`.sts/`, `.apr/`). One PR comment that tells the reviewer exactly what changed, what to test, and what to look at.

## Why each tool is sized this way

### `repox` is a model, not a linter

Most "code intelligence" tools are tied to an editor or a CI vendor. `repox` is a small Python CLI that emits a portable artifact (`.repox/architecture.json`) downstream tools consume. The tree-sitter grammars handle JavaScript and TypeScript natively — no need for a language server.

- **Files, imports, symbols, call edges** — the four primitives every other DevTrust tool needs.
- **No hidden state.** The artifact is JSON. Anything else can read it.
- **Tree-sitter-required as of v0.3** so JS/TS isn't a second-class citizen.

### `sts` reads the architecture, not the code

Test selectors that re-parse Python on every run are slow and error-prone. `sts` consumes `repox`'s architecture model and asks: "which tests transitively reach the changed files?" The answer is fast (graph walk), framework-agnostic (`sts` handles pytest, unittest, jest, vitest, gotest, cargo), and produces a structured verdict file CI can pipe directly into the test runner.

- **Manifest-aware.** A `pyproject.toml` change means run all the tests; a single-file change means just the affecting subset.
- **Naming-convention + mirror-tree + sibling-test detection.** Three independent affecting strategies merged.
- **No false confidence.** When the architecture model isn't available (`--no-use-repox`), `sts` falls back to filename heuristics and explicitly downgrades the verdict.

### `apr` is deterministic-first, LLM-second

Most AI PR reviewers send the entire diff to a model and trust whatever comes back. That's expensive, slow, and non-reproducible. `apr` runs deterministic rules first — they catch the actual common AI-introduction patterns (hardcoded secrets, hallucinated calls, leftover `console.log`, broad excepts) — and only then optionally calls Anthropic to ask "does the PR description match the diff?"

- **`ai-review:hallucinated-symbol`** is fully deterministic. It walks `repox`'s call graph in changed files and flags callees that don't resolve. No API key needed.
- **`ai-review:diff-comprehension`** is LLM-backed and opt-in. Default off; ~$0.005/PR at Sonnet pricing when on.
- **JS + TS rule pack** for the cases where AI assistance is most often used (frontend code).
- **Vendor IDs are silenced.** A model can return whatever rule_id it wants; `apr` re-emits all findings under its own namespace so vendor strings can't leak into reports.

## What this is NOT

- **Not a code formatter.** Use `ruff` / `prettier` / `gofmt` for that.
- **Not a hosted service.** Wave 2 (`sts-app`, `apr-app`) is the GitHub App layer that hosts the engines on PRs, but the Wave 1 engines themselves are libraries + CLIs.
- **Not coupled.** Each tool stands alone. `repox` works without `sts` or `apr`. `sts` and `apr` work without `repox` (with reduced fidelity, honestly downgraded).

## Status — May 2026

| Package | Version | Status |
|---|---|---|
| `devtrust-repox` | v0.4.0 | beta — full Python + JS/TS extraction with call edges, on PyPI |
| `devtrust-sts`   | v0.0.3 | alpha — transitive-import-aware affecting, on PyPI |
| `devtrust-apr`   | v0.2.0 | beta — deterministic Python + JS/TS rules + AI rule pack, on PyPI |

All three pass `mypy --strict` + `ruff check` + `ruff format --check`. Apache-2.0. CI matrix tests on Linux + Windows + macOS across Python 3.11–3.14.

## Where this fits in the broader DevTrust thesis

Wave 1 (`repox` + `sts` + `apr`) is the **trust layer for AI-augmented development**: codebase model, test selection, PR review.

Wave 2 (`sts-app` + `apr-app`) is the **ship layer**: GitHub Apps that bring Wave 1 to every PR, with sticky comments and webhook auth.

Wave 3 (`agtrace` + `whychanged` + `tokencost`) is the **observability layer**: when something goes wrong in production, what changed, what did the agent do, what did it cost.

Wave 4 (`agentguard`) is the **governance layer**: runtime policy enforcement so the agents you ship can't do what they're not allowed to.

Together they form **the trust stack for AI-era engineering — from PR to production.**

## Try it

```bash
# Install all three:
pip install devtrust-repox devtrust-sts devtrust-apr

# In any repo:
repox build .
# -> .repox/architecture.json + .repox/architecture.md

sts info --repo .
# -> table of test files by framework

sts select --repo . --changed src/foo.py --use-repox
# -> .sts/selection.json + .sts/selection.md

apr review --repo . --title "Add feature X" --description "Adds the X widget."
# -> .apr/review.json + .apr/review.md
```

Three commands. Three artifacts. The whole trust layer for one PR.
