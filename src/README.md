# DevTrust

> The trust stack for AI-era engineering — from PR to production.

DevTrust is a connected platform of 8 developer tools, organized into two product lines (**SHIP** for pre-merge code quality, **RUN** for production AI trust) on a shared foundation. Built and shipped in 4 waves over 12 months by a small team.

---

## What's in this repository

This is the **planning workspace** for the DevTrust platform — not the product code itself. It contains:

| Folder | Purpose |
|---|---|
| `docs/` | Master plan (Word + Markdown), roadmap, decisions log |
| `products/` | One-pager spec for each of the 8 products + shared platform |
| `waves/` | Quarter-by-quarter execution plan for the 4 build waves |
| `memory/` | Long-lived context for AI assistants working on this project |
| `.claude/` | Claude Code / Cowork environment (settings, commands, agents) |

When the actual product code starts (Wave 1), each `products/NN-name/` folder will gain a `code/` subdirectory or be moved into its own repository, depending on the lane (OSS goes to its own public repo, paid SaaS lives in a monorepo).

---

## The 8 products

| # | Product | Lane | Wave | Line |
|---|---|---|---|---|
| 1 | **Repo X-ray** | OSS · foundation | 1 | SHIP |
| 2 | **Smart Test Selector** | Paid · lead bet | 1 | SHIP |
| 3 | **Agent-PR Reviewer** | Paid | 2 | SHIP |
| 4 | **CI Local** | OSS | 2 | SHIP |
| 5 | **Dep Upgrade Pilot** | Paid | 4 | SHIP |
| 6 | **Agent Trace SDK** | OSS · foundation | 3 | RUN |
| 7 | **WhyChanged** | OSS | 3 | RUN |
| 8 | **TokenCost** | Paid | 3 | RUN |
| 9 | **AgentGuard** | Paid · enterprise | 4 | RUN |

Read [`docs/DevTrust-Master-Plan.md`](docs/DevTrust-Master-Plan.md) for the full plan. The Word version is [`docs/DevTrust-Master-Plan.docx`](docs/DevTrust-Master-Plan.docx).

---

## How to use this workspace

1. **Skim the master plan** in `docs/` — start there.
2. **Open the dashboard** at `docs/dashboard.html` in a browser to see all products at a glance with scoring and dependencies.
3. **Drill into a product** via `products/NN-name/PRODUCT.md`.
4. **Check the next wave** via `waves/wave-N-*.md` to see what's actively shipping.
5. **Track tasks** in `TASKS.md` (root). Update as you progress.

---

## Status

- **Phase:** Planning · pre-Wave 1
- **Last updated:** 2026-05
- **Owner:** Abdullah Bakir ([github.com/AbdullahBakir97](https://github.com/AbdullahBakir97))

## Existing assets that accelerate the plan

Four of Abdullah's existing GitHub repos are direct head-starts for DevTrust products. See [`memory/project-github-assets.md`](memory/project-github-assets.md) for full mapping.

| Existing | Powers | Time saved |
|---|---|---|
| [`ai-quality-gate`](https://github.com/AbdullahBakir97/ai-quality-gate) + [`pr-coach`](https://github.com/AbdullahBakir97/pr-coach) + [`commit-craft`](https://github.com/AbdullahBakir97/commit-craft) | Agent-PR Reviewer (Wave 2) | 4–6 weeks |
| [`Repo-Directory-Structure`](https://github.com/AbdullahBakir97/Repo-Directory-Structure) + [`repodoc-ai`](https://github.com/AbdullahBakir97/repodoc-ai) | Repo X-ray (Wave 1) | 3–4 weeks |
| [`cortex`](https://github.com/AbdullahBakir97/cortex) | Shared agent runtime (Wave 1) | 1–2 weeks |
| [`issue-triage-bot`](https://github.com/AbdullahBakir97/issue-triage-bot) | Year 2 product candidate | n/a |

**Net impact:** roughly 8–12 weeks of build time reclaimed across Waves 1 and 2.
