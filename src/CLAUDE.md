# CLAUDE.md — DevTrust working memory

> This file is loaded into every AI assistant conversation in this workspace.
> Keep it under 200 lines. Heavier context lives in `memory/`.

## The 30-second pitch

DevTrust is a connected platform of 8 developer tools, organized as **two product lines on shared foundations**:

- **SHIP** — pre-merge code quality (Repo X-ray, Smart Test Selector, Agent-PR Reviewer, CI Local, Dep Upgrade Pilot)
- **RUN** — production AI trust (Agent Trace SDK, WhyChanged, TokenCost, AgentGuard)

The whole platform answers one question for engineering teams: *"How do we keep AI-augmented code trustworthy from the moment it's written to the moment it runs?"*

## The bet (single sentence)

The next decade of dev tools will be won by products that make AI-augmented development trustworthy and observable — not by products that make code generation marginally faster.

## Operating mode (May 2026 onward — Build Mode)

DevTrust is no longer following the wave-driven validation plan. Read [`docs/BUILD-MODE.md`](docs/BUILD-MODE.md) before any work decision. In short:

- **No time gates, no external validation.** Build everything to a professional bar. Internal testing only (Abdullah + one developer friend).
- **The "professional" bar is concrete.** Defined in [`docs/DEFINITION-OF-DONE.md`](docs/DEFINITION-OF-DONE.md). Three tiers: Scaffold (A), Beta (B), Release (C). No skipping checkboxes without written justification in the product's CHANGELOG.
- **Order is technical-dependency-driven, not wave-driven.** Foundations first (Repo X-ray, Agent Trace SDK), then their dependents. Live order at [`docs/BUILD-QUEUE.md`](docs/BUILD-QUEUE.md).
- **The wave plans stay** as the public-launch playbook for later. Same with the 30-day validation plays in the master plan §8 — those will activate when we decide to ship publicly.

## How to think about choices in this workspace

- **One platform, not eight startups.** Every decision should reduce the work of building the next product, not just the current one.
- **OSS earns audience, paid earns revenue.** Free OSS primitives drive distribution; paid SaaS captures recurring revenue. Don't confuse the lanes.
- **Quality gates are now Definition-of-Done.** Wave/timing pressure is suspended; quality bar is not.
- **Concrete > clever.** "We cut CI from 28 → 9 minutes" beats "we leverage AI for test optimization" every time.

## Working preferences (from the user)

- Speak directly. Skip apologies and self-narration.
- Concrete examples > abstract principles.
- Show numbers wherever possible.
- Spelling: the user is fluent in English but not native. Don't correct spelling unless asked.
- Output format: prose for explanations, tables for comparisons, lists when the user asks for them.

## Repo layout (after May 2026 move into a Python monorepo)

The DevTrust workspace now lives inside a Python monorepo:

```
C:\Users\abdul\Projects\DevTrust\
├── .venv/                         Python 3.14.2 venv
├── pyproject.toml                 Workspace umbrella (uv workspace + shared dev tooling)
├── .python-version
├── README.md                      Top-level README
└── src/                           ← THIS folder (the planning workspace)
    ├── CLAUDE.md                  ← this file
    ├── README.md, TASKS.md, LICENSE
    ├── docs/, memory/, waves/
    └── products/
        └── NN-name/
            ├── PRODUCT.md         Spec
            └── code/              Python package (added per wave)
```

Per-product Python code lives at `src/products/NN-name/code/` with a standard `pyproject.toml` + `src/<package>/` + `tests/` layout. Each product is a uv workspace member.

Repo X-ray (Wave 1) is the first product with code. Its package is `repox` and you can run `python -m repox build` from anywhere in the monorepo.

## File-finding shortcuts

| Want... | Open... |
|---|---|
| The full plan | `docs/DevTrust-Master-Plan.md` (or `.docx`) |
| One product's spec | `products/NN-name/PRODUCT.md` |
| One product's code | `products/NN-name/code/src/<package>/` |
| What ships when | `waves/wave-N-*.md` |
| Visual overview | `docs/dashboard.html` |
| What's left to do | `TASKS.md` |
| Long-term context | `memory/MEMORY.md` (index → individual memory files) |

## Glossary

- **SHIP** = pre-merge product line (PRs, CI, test suites, code review)
- **RUN** = production product line (telemetry, governance, cost, incidents)
- **Wave 1–4** = 12-month rollout plan, 3 months each
- **OSS lane** = open-source product, distribution moat
- **Paid lane** = commercial SaaS, revenue moat
- **Lead bet** = the highest-priority product in a wave (Wave 1 lead bet = Smart Test Selector)
- **Foundation** = shared primitive that powers multiple products (Repo X-ray, Agent Trace SDK)

## Don't do

- Don't suggest building a "better LangChain" or generic agent framework. That ship has sailed.
- Don't propose merging products into one mega-tool. The two-line structure is intentional and customer-facing.
- Don't suggest abandoning the OSS half for pure SaaS. The OSS distribution channel is load-bearing.
- Don't rewrite the wave order without an explicit user decision. Sequencing dependencies are documented.
