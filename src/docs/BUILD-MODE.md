# DevTrust — Build Mode (operating model from May 2026 onward)

> **Decision date:** 2026-05-05
> **Decided by:** Abdullah Bakir (project owner)
> **Replaces:** the wave-driven validation playbook in `src/waves/wave-N-*.md` as the day-to-day operating reference.

---

## What changed

The original plan (master plan v1, May 2026) sequenced 9 products across 4 waves of ~3 months each, with 30-day validation gates and explicit kill criteria at every wave boundary. That plan was built around shipping publicly, finding paying design partners, and managing risk under a tight runway.

The owner has explicitly redirected: **build everything to a professional standard, with internal testing only, until the platform is feature-complete across all 9 products**. Public launch and external validation come later — they are not suspended permanently, just deferred until the build is done.

## What this changes in practice

| Concern | Old model | Build mode (now) |
|---|---|---|
| Time pressure | 12-month, wave-bounded | None — work until done at quality bar |
| External validation | 30-day playbook per product, kill criteria | None during build phase |
| Order of work | Risk-managed wave order | Technical-dependency order |
| Testing | Design partners on closed beta | Owner + one developer friend |
| Quality bar | "MVP that proves the bet" | Definition-of-Done in `DEFINITION-OF-DONE.md` |
| Public release | End of each wave | After whole platform is at DOD |

## What does NOT change

- **The 9-product platform thesis.** SHIP and RUN lines, two foundations, shared infrastructure — same architecture.
- **The product specs.** `src/products/NN-name/PRODUCT.md` are the source of truth for what each product does.
- **The master plan document.** `src/docs/DevTrust-Master-Plan.docx` remains the strategic narrative — readers just need to know that timing has been suspended.
- **The wave plans.** `src/waves/wave-N-*.md` are preserved as the **launch playbook** — when the build is complete and we're ready to ship publicly, those waves describe the GTM motion to follow.

## New operating loop

Per work session:

1. **Pick one product** to advance. Order is set by `BUILD-QUEUE.md` (this folder).
2. **Pick the next version** — usually one minor or patch step (`v0.0.2 → v0.1`).
3. **Hit Definition-of-Done** for that version before moving on.
4. **Update `CHANGELOG.md`** for that product, bump the version, ensure tests pass.
5. **Move on** to the next item in the queue.

Reviews happen continuously: the owner runs the new version against real workspaces and reports issues. The friend-tester is brought in at major version boundaries (v0.1, v0.5, v1.0).

## Build queue (current order — re-derived from technical dependencies)

This replaces wave-driven order. It groups by what unblocks what.

### Phase 1 — Foundations to v1.0 (everything depends on these)

1. **Repo X-ray** v0.0.2 → v0.1 → v0.5 → v1.0 — codebase model that powers half the products
2. **Agent Trace SDK** scaffold → v0.1 → v0.5 → v1.0 — telemetry standard that powers RUN cluster

### Phase 2 — Products built on Repo X-ray (SHIP cluster)

3. **Smart Test Selector** scaffold → v0.1 → v0.5 → v1.0
4. **Agent-PR Reviewer** scaffold → v0.1 → v0.5 → v1.0 (reuses ai-quality-gate, pr-coach, commit-craft)
5. **Dep Upgrade Pilot** scaffold → v0.1 → v0.5 → v1.0

### Phase 3 — Products built on Agent Trace SDK (RUN cluster)

6. **WhyChanged** scaffold → v0.1 → v0.5 → v1.0
7. **TokenCost** scaffold → v0.1 → v0.5 → v1.0
8. **AgentGuard** scaffold → v0.1 → v0.5 → v1.0

### Phase 4 — Standalone

9. **CI Local** scaffold → v0.1 → v0.5 → v1.0 — no DevTrust foundation dependency

### Phase 5 — Shared web platform

10. **Shared platform infrastructure** — auth, billing, agent runtime, unified dashboard. Built only when the first hosted product needs it (not before).

## Where the old playbook lives

- `src/waves/wave-1-foundation.md` — launch playbook for the foundation + lead bet, when we're ready to ship publicly
- `src/waves/wave-2-expand-ship.md` — same, for SHIP expansion
- `src/waves/wave-3-open-run.md` — same, for opening RUN line
- `src/waves/wave-4-compliance.md` — same, for enterprise sales motion
- `src/docs/DevTrust-Master-Plan.docx` — strategic narrative; readers reference §8 (validation playbook) and §9 (GTM playbook) when going public

## Risks to watch

- **Loss of external validation signal.** If a product turns out to solve a non-problem, we'll find out later than the wave plan would have caught it. Mitigation: the owner's friend-tester is a fresh pair of eyes; bring them in at every major version.
- **Polish creep.** Without time gates, "one more thing" can become forever. Mitigation: Definition-of-Done is checked off; if a "nice to have" isn't on it, log it as a v.next idea and move on.
- **Resource drift.** A small team can build to a quality bar across 9 products if they're patient, but burnout is real. Mitigation: track progress against `BUILD-QUEUE.md`, take real breaks.
