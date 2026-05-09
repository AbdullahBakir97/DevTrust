# Contributing to DevTrust

Thanks for your interest. DevTrust is a connected platform of 9 developer tools. The contributing experience is the same regardless of which product you're working on; this guide gets you set up and outlines the bar all changes must clear before merge.

---

## Quick start

```powershell
# 1. Fork and clone (replace with your fork once forked).
git clone https://github.com/AbdullahBakir97/DevTrust.git
cd DevTrust

# 2. One-time tooling install. uv is required; pre-commit is strongly recommended.
#    Install uv: https://docs.astral.sh/uv/getting-started/installation/
uv venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate        # macOS / Linux
uv sync --all-packages --all-groups

# 3. Activate pre-commit hooks (lint, format, type-check, conventional commits).
uv run pre-commit install --install-hooks --hook-type commit-msg

# 4. Run tests once to confirm setup.
uv run pytest
```

You're ready. Make a branch off `main`, write your change, push, open a PR.

---

## Where to work

```
src/
├── docs/                                  Master plan, dashboard, BUILD-MODE, DOD
├── memory/                                Long-lived context (read on every AI session)
├── waves/                                 Public-launch playbook (frozen during build mode)
└── products/
    ├── 00-shared-platform/                Spec for shared infra (auth, billing, etc.)
    └── NN-name/
        ├── PRODUCT.md                     Spec — the source of truth for what the product does
        └── code/                          Python package + tests
            ├── pyproject.toml
            ├── src/<package>/
            └── tests/
```

For each new feature or bug fix:

1. **Read the product's `PRODUCT.md`** — it's the spec; if your change conflicts, propose an update to the spec in the same PR.
2. **Bump the package version** in `pyproject.toml` and `__init__.py` if your change is user-visible.
3. **Update `CHANGELOG.md`** under `[Unreleased]` with a one-line entry.

---

## The bar

All PRs must clear [`src/docs/DEFINITION-OF-DONE.md`](src/docs/DEFINITION-OF-DONE.md) for the tier the product is currently at. CI enforces the bar — your PR will fail if any of these are wrong:

- `ruff check` clean
- `ruff format --check` clean
- `mypy` strict clean
- `pytest` green on Python 3.11/3.12/3.13/3.14 across Linux/Windows/macOS
- Coverage ≥ 85% on the changed package (Tier B+)

You can run all of these locally:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=src/products
```

---

## Commit message style

We use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). The pre-commit `commit-msg` hook will refuse messages that don't conform.

Format: `<type>(<scope>): <subject>`

Examples:

```
feat(repox): add Cargo.toml manifest parser
fix(repox): dedupe entry points when manifest declares the conventional name
docs(repox): add Tier B feature list to README
chore(workspace): bump pre-commit hooks to v5.0.0
```

Scopes:
- Per-product: `repox`, `sts` (smart-test-selector), `apr` (agent-pr-reviewer), `cilocal`, `depup`, `trace` (agent-trace-sdk), `whychanged`, `tokencost`, `agentguard`, `shared`
- Workspace: `workspace`, `ci`, `docs`, `memory`

---

## Pull request flow

1. Branch from `main`. Branch name format: `<scope>/<short-description>` (e.g. `repox/cargo-parser`).
2. Push and open a PR. The template will guide you through the DoD checklist.
3. CI runs automatically. Fix any failures.
4. A maintainer reviews. Address comments by pushing more commits to the branch (don't force-push during review).
5. Once approved, the maintainer squash-merges with a clean conventional-commit message.

---

## Reporting bugs

Use the [bug report template](https://github.com/AbdullahBakir97/DevTrust/issues/new?template=bug_report.yml).

For security issues, follow [SECURITY.md](SECURITY.md) — **do not open a public issue**.

---

## Questions

Open a GitHub Discussion: <https://github.com/AbdullahBakir97/DevTrust/discussions>.

Welcome aboard.
