## What this PR does

<!-- One-paragraph summary. What changed and why. -->

## Product(s) touched

<!-- Tick all that apply. -->

- [ ] Repo X-ray (`src/products/01-repo-xray`)
- [ ] Smart Test Selector (`src/products/02-smart-test-selector`)
- [ ] Agent-PR Reviewer (`src/products/03-agent-pr-reviewer`)
- [ ] CI Local (`src/products/04-ci-local`)
- [ ] Dep Upgrade Pilot (`src/products/05-dep-upgrade-pilot`)
- [ ] Agent Trace SDK (`src/products/06-agent-trace-sdk`)
- [ ] WhyChanged (`src/products/07-whychanged`)
- [ ] TokenCost (`src/products/08-tokencost`)
- [ ] AgentGuard (`src/products/09-agentguard`)
- [ ] Shared platform (`src/products/00-shared-platform`)
- [ ] Workspace tooling (root config, CI, docs, memory)

## Definition-of-Done checklist

(See [`src/docs/DEFINITION-OF-DONE.md`](../src/docs/DEFINITION-OF-DONE.md) for the full bar.)

- [ ] Tests added / updated and passing locally
- [ ] `ruff check` clean
- [ ] `ruff format --check` clean
- [ ] `mypy` strict clean (where applicable to changed files)
- [ ] Changelog entry added under `[Unreleased]`
- [ ] Schema bump documented if any data model changed
- [ ] No TODO comments without an associated task in `src/TASKS.md`

## How to verify

<!-- Concrete commands a reviewer can run. -->

```powershell
uv sync --all-packages --all-groups
uv run pytest
uv run ruff check .
uv run mypy
```

## Notes / open questions

<!-- Anything you want a second opinion on. -->
