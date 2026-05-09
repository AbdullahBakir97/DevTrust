# DevTrust — Build queue

> Live, in-order list of what gets built next. Replaces wave-driven sequencing during build mode.
>
> **One product advances at a time.** The next item is the top one not marked done.
> When it hits its target tier in `DEFINITION-OF-DONE.md`, mark it done and move on.

Last updated: 2026-05-05

---

## Phase 1 — Foundations

These power the SHIP and RUN clusters. Everything else waits on these.

| # | Product | At | Next | Target tier |
|---|---|---|---|---|
| 1 | Repo X-ray | v0.0.2 (Tier A) | v0.1: manifest parsing, dep graph, conventions | Tier B |
| 2 | Agent Trace SDK | not scaffolded | scaffold → v0.0.1 (Tier A) | Tier A |

## Phase 2 — SHIP cluster (built on Repo X-ray)

| # | Product | At | Next | Target tier |
|---|---|---|---|---|
| 3 | Smart Test Selector | not scaffolded | scaffold → v0.0.1 | Tier A |
| 4 | Agent-PR Reviewer | not scaffolded | port from `ai-quality-gate` + `pr-coach` + `commit-craft` → v0.0.1 | Tier A |
| 5 | Dep Upgrade Pilot | not scaffolded | scaffold → v0.0.1 | Tier A |

## Phase 3 — RUN cluster (built on Agent Trace SDK)

| # | Product | At | Next | Target tier |
|---|---|---|---|---|
| 6 | WhyChanged | not scaffolded | scaffold → v0.0.1 | Tier A |
| 7 | TokenCost | not scaffolded | scaffold → v0.0.1 | Tier A |
| 8 | AgentGuard | not scaffolded | scaffold → v0.0.1 | Tier A |

## Phase 4 — Standalone

| # | Product | At | Next | Target tier |
|---|---|---|---|---|
| 9 | CI Local | not scaffolded | scaffold → v0.0.1 | Tier A |

## Phase 5 — Shared web platform

| # | Product | At | Next | Target tier |
|---|---|---|---|---|
| 10 | Shared platform infra | not scaffolded | defer until first product needs hosted features | n/a |

---

## Sweep order across phases

After every product reaches **Tier A (scaffold)**, sweep again to push everything from Tier A to **Tier B**. Then sweep again from Tier B to **Tier C**. This is breadth-first, not depth-first — it keeps the platform feature-coherent rather than deeply polishing one product while the others rot.

Approximate session count for one full sweep:

| Sweep | Output | Approx sessions (small team, no time pressure) |
|---|---|---|
| Sweep 1: Tier A on every product | 9 scaffolded products, smoke tests | ~15 sessions |
| Sweep 2: Tier B | Full feature set, CI, mypy strict, 85% coverage everywhere | ~30 sessions |
| Sweep 3: Tier C | Hardened, benchmarked, signed, doc site, ready to publish | ~20 sessions |

Numbers are estimates, not commitments. Each session = one focused work block.

---

## What we're working on RIGHT NOW

**Active:** Repo X-ray v0.0.2 → v0.1
**Owner:** Abdullah (with Claude as build partner)
**Tester:** Abdullah + one developer friend (TBD intro)
