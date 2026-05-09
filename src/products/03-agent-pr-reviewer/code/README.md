# Agent-PR Reviewer (`apr`)

> Deterministic + AI-pattern review for pull requests. Wave 2 lead bet of the DevTrust connected platform.

## Status

**v0.2.0 beta** — deterministic Python + JS/TS rules, deterministic AI-pattern checker (`ai-review:hallucinated-symbol`) now multi-language via Repo X-ray v0.4 call edges, plus optional LLM-backed `ai-review:diff-comprehension` (Anthropic).

## Why

Three of your existing GitHub Apps — `ai-quality-gate`, `pr-coach`, `commit-craft` — each solve part of "make PR review better" but ship as separate apps with separate auth, separate webhooks, separate UIs. `apr` consolidates them into one engine so:

- One install. One webhook. One sticky comment per PR.
- Deterministic rules first (testable, gradeable, cheap), LLM layer second.
- Reuses Repo X-ray's architecture model for file context.

## Rules shipped through v0.0.2

### Python (`.py`)

| Rule ID | Severity | Category | What it catches |
|---|---|---|---|
| `bare-except` | warning | quality | `except:` without an exception class |
| `print-debug` | info | quality | leftover `print(...)` calls (skipped in `__main__` guard files) |
| `todo-no-ticket` | info | todo | TODO/FIXME/XXX/HACK without `#123` / `PROJ-123` reference |
| `empty-function-body` | info | ai-pattern | function body is only `pass` |
| `syntax-error` | error | quality | file does not parse |
| `mutable-default-arg` | warning | quality | `def f(x=[])` shares state across calls |
| `broad-except` | info | quality | `except Exception:` is broader than most code needs |
| `assert-in-prod` | warning | security | `assert` is stripped under `python -O`. Test files exempt. |
| `hardcoded-secret` | critical | security | AWS / GitHub / OpenAI / Anthropic / Slack tokens, inline credential literals |

### JavaScript / TypeScript (`.js .jsx .mjs .cjs .ts .tsx`) — v0.0.2+

| Rule ID | Severity | Category | What it catches |
|---|---|---|---|
| `console-log` | info | quality | leftover `console.log/debug/info`. Skipped in entry files (`process.argv`, `.listen(`, `import.meta.main`). |
| `debugger-statement` | warning | quality | `debugger;` left in code |
| `var-declaration` | info | style | `var` instead of `let`/`const` |
| `todo-no-ticket` | info | todo | mirror of the Python rule |

### PR-level

| Rule ID | Severity | Category | What it catches |
|---|---|---|---|
| `pr-title-uninformative` | warning | commit | PR title too short or one of `wip`/`draft`/`tmp`/`test` |
| `pr-description-too-short` | info | commit | PR description under 30 characters |

### AI-pattern (opt-in via `--enable-ai`) — v0.1.0+ / v0.2.0 multi-language

| Rule ID | Severity | Category | What it catches |
|---|---|---|---|
| `ai-review:hallucinated-symbol` | warning | ai-pattern | A function call whose name doesn't resolve to an in-repo symbol, an imported alias, or a known stdlib / global / popular package root. **Now spans Python + JS/TS as of v0.2.0.** Requires `.repox/architecture.json` (run `repox` first). |
| `ai-review:diff-comprehension` | warning/info | ai-pattern | LLM-backed check for "does the PR description accurately describe the diff?". Pass `--ai-provider anthropic` and set `ANTHROPIC_API_KEY`. |

## CLI

```bash
apr version
apr review --repo .
apr review --repo . --changed src/foo.py --changed src/bar.py
apr review --repo . --title "Fix nullable fields" --description "..."
```

Output: `.apr/review.json` (schema-versioned, machine-readable) + `.apr/review.md` (human companion).

## Roadmap

- ✅ **v0.0.2** — JS/TS rule pack (`console-log`, `debugger-statement`, `var-declaration`, `todo-no-ticket`).
- ✅ **v0.1.0** — AI rule pack: deterministic `ai-review:hallucinated-symbol` + LLM-pluggable `ai-review:diff-comprehension`.
- ✅ **v0.1.1** — real Anthropic backend for `ai-review:diff-comprehension`.
- ✅ **v0.2.0** — `ai-review:hallucinated-symbol` extended to JS/TS via repox v0.4 call edges. APR now covers all three Wave-1 languages.
- **v0.3.0** (next) — auto-suggest fixes via the GitHub Suggested Changes API; per-import `local_names` for renamed JS imports.

## Status

Apache-2.0. See [CHANGELOG](CHANGELOG.md).
