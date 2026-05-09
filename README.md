# DevTrust

> The trust stack for AI-era engineering — from PR to production.

DevTrust is a connected platform of small, opinionated, production-grade tools that give engineering teams a coherent answer to a simple question: **as AI starts to write more of the code, how do we keep trust in what ships?**

Each tool stands alone, ships to PyPI independently, and works with nothing but `pip install`. They also compose: the architecture model from one product feeds the test selector in the next, which feeds the PR reviewer after that, which feeds incident response when something breaks. Three full waves are shipped; a fourth is queued.

---

## What's in here

Eight installable packages across three shipped waves, each with its own `pyproject.toml`, `README.md`, `CHANGELOG.md`, tests, and PyPI release.

### Wave 1 — codebase understanding

| Package | What it does | Latest |
|---|---|---|
| [`repox`](src/products/01-repo-xray/code/) | Build a portable architecture model of any codebase: files, imports, symbols, and function-call edges across Python + JavaScript + TypeScript via tree-sitter. Emits `.repox/architecture.{json,md}` that downstream tools consume. | **0.4.0** |
| [`sts`](src/products/02-smart-test-selector/code/) | Smart Test Selector: given a code change, decide which tests must run. Transitive-import-aware, framework-detection (pytest, unittest, jest, vitest), reads `repox` artifacts when available. | **0.0.3** |
| [`apr`](src/products/03-agent-pr-reviewer/code/) | Agent-PR Reviewer: deterministic + AI-pattern review for pull requests. Python + JS/TS rule packs, plus opt-in LLM-backed `ai-review:diff-comprehension` (Anthropic) and a deterministic `ai-review:hallucinated-symbol` rule that walks `repox` call edges to flag invented function calls. | **0.2.0** |

### Wave 2 — ship surfaces

| Package | What it does | Latest |
|---|---|---|
| [`sts-app`](src/products/02-smart-test-selector/app/) | GitHub App for `sts`. JWT-signed installation tokens, HMAC webhook verification, tarball clone (no `git` binary needed), runs `repox` + `sts` end-to-end and posts a sticky PR comment with the verdict. | **0.0.3** |
| [`apr-app`](src/products/03-agent-pr-reviewer/app/) | GitHub App for `apr`. Same shape as `sts-app` — webhook receiver, GitHub App auth, sticky PR comment with findings. | **0.0.1** |

### Wave 3 — open & run

| Package | What it does | Latest |
|---|---|---|
| [`agtrace`](src/products/06-agent-trace-sdk/code/) | Agent-aware tracing for LLM-driven workflows: spans, events, tool calls, JSONL append-only event store, ContextVar-based attribution that's safe across threads + async. | **0.0.2** |
| [`whychanged`](src/products/07-whychanged/code/) | Production diff-detective for incident response: when something breaks, rank the changes most likely to be the culprit. Pluggable `ChangeProvider` interface (git history + GitHub Deployments shipped). | **0.1.0** |
| [`tokencost`](src/products/08-tokencost/code/) | Financial-grade attribution for LLM spend: capture every Anthropic / OpenAI call with team / user / feature attribution, money in integer micro-USD (no float drift), JSONL store + cost report. Composes with `agtrace` so cost attaches to the active agent span. | **0.0.3** |

→ See [`docs/wave-3-overview.md`](docs/wave-3-overview.md) for the trio explainer.

### Wave 4 — queued

[`agentguard`](src/products/09-agentguard/PRODUCT.md) — runtime governance + policy-as-code for AI agent tools. Spec written; build pending.

---

## Why one repo

Independent versions, one source of truth. Cross-package changes (`apr` depends on `repox` artifacts; `tokencost` writes spans into the active `agtrace` context) land in one PR, get reviewed together, and ship as a coherent platform release. Each package still publishes to PyPI independently — `release.yml` fires on `<package>-v<version>` tags and publishes that package only.

---

## Getting started

### Prerequisites

- Python 3.11+ (workspace pinned to 3.14.2 in `.python-version`)
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`

### One-time setup

```powershell
git clone https://github.com/AbdullahBakir97/DevTrust.git
cd DevTrust

uv venv
.venv\Scripts\activate
uv sync --all-packages --all-groups
```

### Smoke check

```powershell
# Lint, format, type-check, all tests, version + changelog gates
uv run python scripts/release.py --check
```

This is the same gate `release.yml` runs in CI before publishing to PyPI. A clean run looks like:

```
== Per-package metadata check ==
  ok    repox      @ 0.4.0
  ok    sts        @ 0.0.3
  ok    sts-app    @ 0.0.3
  ok    apr        @ 0.2.0
  ok    apr-app    @ 0.0.1
  ok    agtrace    @ 0.0.2
  ok    whychanged @ 0.1.0
  ok    tokencost  @ 0.0.3
== Workspace gates ==
  ok    ruff check
  ok    ruff format --check
  ok    mypy --strict
== Per-package tests ==
  ok    repox       33 passed
  ok    sts         30 passed
  ok    sts-app     29 passed
  ok    apr         53 passed, 4 skipped
  ok    apr-app     22 passed
  ok    agtrace     18 passed
  ok    whychanged  31 passed
  ok    tokencost   36 passed
READY TO RELEASE
```

### Try a single tool

```powershell
# Build an architecture model of any repo
repox build C:\path\to\some\repo

# Pick which tests should run for a change set
sts select --repo . --changed src\products\01-repo-xray\code\src\repox\analyzer.py

# Review a PR locally before pushing
apr review --repo . --title "Fix nullable fields" --description "..."

# Find culprits for an incident
whychanged explain --repo . --since 30m --service api

# Show LLM cost attribution
tokencost report --since 1d
```

---

## Releases & PyPI

Each package versions independently. Tag format: `<package>-v<version>` (e.g. `apr-v0.2.0`, `repox-v0.4.0`). Tags trigger [`release.yml`](.github/workflows/release.yml) which:

1. Re-runs the full preflight (`scripts/release.py --check`).
2. Builds wheel + sdist with `uv build --package <name>`.
3. Publishes via [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC, no long-lived API tokens).

See [`RELEASE.md`](RELEASE.md) for the full process, including one-time PyPI Trusted Publisher setup per package.

---

## Security & responsible disclosure

See [`SECURITY.md`](SECURITY.md). In short: do not file public issues for security bugs; email the address in `SECURITY.md` and we'll respond.

API keys, GitHub App private keys, webhook secrets, and PyPI tokens are never committed to this repo. Local development uses `.env` files (gitignored). CI uses GitHub Actions secrets. PyPI publishing uses Trusted Publishing — no PyPI API tokens exist anywhere in this codebase.

---

## Documentation

- **Wave overviews:** [`src/waves/`](src/waves/) — narrative plans for each wave
- **Per-product specs:** `src/products/NN-name/PRODUCT.md`
- **Per-package READMEs:** `src/products/NN-name/code/README.md` (and `app/README.md` for the GitHub App variants)
- **Wave 3 explainer:** [`docs/wave-3-overview.md`](docs/wave-3-overview.md)
- **Master plan:** [`src/docs/`](src/docs/)

---

## Status

| Wave | State | Packages |
|---|---|---|
| Wave 1 (codebase understanding) | **Shipped** | `repox` 0.4.0, `sts` 0.0.3, `apr` 0.2.0 |
| Wave 2 (ship surfaces) | **Shipped** | `sts-app` 0.0.3, `apr-app` 0.0.1 |
| Wave 3 (open & run) | **Shipped** | `agtrace` 0.0.2, `whychanged` 0.1.0, `tokencost` 0.0.3 |
| Wave 4 (compliance & governance) | Spec only | `agentguard` (pending) |

License: Apache-2.0. Owner: Abdullah Bakir ([github.com/AbdullahBakir97](https://github.com/AbdullahBakir97)).
