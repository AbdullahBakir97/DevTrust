# DevTrust — task list

This file is the living, lightweight to-do list for the DevTrust planning workspace
and the work leading up to Wave 1. Update freely. Move things to the bottom under
**Done** when complete.

Format: `- [ ] Task — owner (@abdullah) — due YYYY-MM-DD — context`

---

## Now (this week)

- [ ] Read the master plan end-to-end and flag anything that disagrees with your gut — @abdullah
- [ ] Pick the GitHub org / handle DevTrust will live under — @abdullah
- [ ] Decide on the brand name (DevTrust working name, or something else) — @abdullah
- [ ] Reserve domain candidates (devtrust.dev, devtrust.io, alternatives) — @abdullah
- [ ] **Audit existing GitHub Apps** — confirm production readiness, license, and test coverage of `ai-quality-gate`, `pr-coach`, `commit-craft`, `Repo-Directory-Structure`, `repodoc-ai`, `cortex`. See `memory/project-github-assets.md`. — @abdullah

## Next (Wave 1 prep — 30 days)

- [ ] Run the 30-day validation playbook on Smart Test Selector (see `waves/wave-1-foundation.md`) — @abdullah
- [ ] Set up landing page for Smart Test Selector waitlist — @abdullah
- [ ] Conduct 10 problem interviews with engineering managers about CI pain — @abdullah
- [x] Stub the Repo X-ray CLI: `repox build` analyzes a repo and emits `.repox/architecture.{json,md}` — done in v0.0.1, hardened in v0.0.2
- [x] Clean up the venv-at-root pollution and re-create at `.venv\` — done; `uv venv` + `uv sync --all-packages --all-groups` is the working recipe
- [ ] Open public GitHub repo for Repo X-ray under chosen org — @abdullah

## Later (Wave 1 build)

- [x] Repo X-ray v0.1 — manifest parsing (pyproject/package.json/Cargo/go.mod), conventions detection (indent, layout, license, config files), expanded language coverage. **mypy strict + ruff clean + 19 tests passing on Python 3.14.2, Windows.**
- [x] Repo X-ray v0.2 — Python `ast`-based call graph: imports + symbols (functions, classes, methods, top-level variables). Schema 0.2.0 (non-breaking). Adds `Architecture.call_graph` with `imports_by_file()` and `files_importing()` helpers. **mypy strict + ruff clean across 26 source files.**
- [ ] Repo X-ray v0.3 — tree-sitter for JS/TS/Go/Rust + function-call edges
- [ ] Smart Test Selector v0.1 — GitHub App that comments suggested tests on PRs
- [x] Smart Test Selector v0.0.2 — Repo X-ray integration (auto-reads `.repox/architecture.json`), package-boundary heuristic for monorepo cases, schema 0.1.0 (non-breaking). +5 tests covering integration + scoping. **mypy strict + ruff clean.**
- [x] Smart Test Selector GitHub App v0.0.1 (`sts-app`) — FastAPI service, HMAC-SHA256 webhook signature verification, async GitHub REST client (no SDK), pull-request event handler with sticky-comment formatter. 17 tests via TestClient + httpx.MockTransport. **mypy strict + ruff clean across 25→26 source files.** Workspace dep on `sts`.
- [x] Tier B parity for sts (CI workflow + monorepo Tier B docs cover both products generically)
- [x] Smart Test Selector v0.0.1 — CLI scaffold (`sts select / version / info`), Pydantic schema 0.0.1, framework detector (pytest/jest/gotest/cargo), affecting engine (manifest-edge / sibling / mirror-tree / naming-convention), JSON + Markdown writers, 17 smoke tests. **mypy strict + ruff clean in sandbox.** Workspace dep on `repox`.
- [x] Smart Test Selector v0.0.2 — repox integration (`repox_integration.py` reads `.repox/architecture.json` for the gitignore-filtered file list), package-boundary heuristic (tests inside the same enclosing manifest as a changed source are must-run), `--use-repox/--no-use-repox` CLI flag. Schema 0.1.0. 26 tests passing. **All gates green on Windows + sandbox.**
- [x] **sts-app v0.0.1** — FastAPI service (`src/products/02-smart-test-selector/app/`) that runs `sts.selector.select()` on every PR and posts a sticky comment. HMAC-SHA256 signature verification (constant-time compare, dev-mode guard), async GitHub REST client (no SDK dep), pydantic-settings config, `/`, `/health`, `/version`, `/webhooks/github` routes, 17 smoke tests covering the security module, comment formatter, and full webhook flow with mocked GitHub API. **mypy strict clean (7 source files), ruff + format clean (10 files).** PEP 561 `py.typed` markers added to `repox`, `sts`, and `sts_app` so downstream consumers get type info. Pending Windows verification.
- [ ] Smart Test Selector v0.2 — flakiness predictor
- [ ] Wire Smart Test Selector to consume Repo X-ray output

## Backlog (post-Wave 1, ordered)

See `waves/wave-2-expand-ship.md`, `waves/wave-3-open-run.md`, `waves/wave-4-compliance.md`.

---

## Done

- [x] Ini