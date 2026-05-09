# 03 — Agent-PR Reviewer

> Code review bot specifically tuned to catch the failure modes of AI-generated PRs.

| | |
|---|---|
| **Lane** | Paid SaaS |
| **Wave** | 2 (months 3–6) |
| **Lead user** | Engineering leads, senior engineers, OSS maintainers |
| **Pricing** | $19/dev/mo, $99/repo/mo for OSS-friendly tier |
| **Depends on** | Repo X-ray · Shared platform |

---

## Pain point

Generic code review bots (CodeRabbit, Greptile, Bito) treat all PRs the same. But AI-generated PRs fail in distinct, recurring ways:

- Hallucinated APIs that look plausible but don't exist
- Duplicated logic instead of refactor (literal-instruction-following)
- Unsafe context handling (unsanitized inputs, missing edge cases)
- Style/convention drift from the rest of the repo
- Subtle correctness bugs the prose around them confidently glosses over

Maintainers also face a flood of low-quality, AI-assisted PRs from new contributors — what GitHub itself called *"a denial-of-service attack on human attention."*

## Target user

- **Primary:** Senior engineers and tech leads at companies where AI-assisted PRs are now common.
- **Secondary:** OSS maintainers managing repos with a high contributor-to-maintainer ratio.
- **Tertiary:** Compliance / security-conscious teams who want a paper trail of AI-PR review.

## Value proposition

*"Code review built for the era when most PRs are written with AI."*

Demo line: **"Catch the things humans miss in AI PRs — and the things AI reviewers don't bother flagging."**

## Key features (MVP)

1. **GitHub App** — installs alongside Smart Test Selector; reuses the same auth and team setup.
2. **AI-failure-mode detectors** — purpose-built rules for hallucinated imports, duplicated logic, missing input validation, convention drift, and inconsistent error handling. Each rule cites the specific evidence from the diff.
3. **Repo X-ray-aware checks** — uses the architecture model to flag PRs that violate documented conventions or break module boundaries.
4. **Provenance hint** — gives a confidence score on whether the PR was AI-generated, partial assist, or fully human. Maintainers configure how this affects review thoroughness.
5. **Severity-aware comments** — distinguishes "this will break production" from "this is a style nit." Aggressive on the former, suggested-only on the latter.
6. **Reviewer assist mode** — instead of auto-commenting, drafts a review the human reviewer can edit and post in one click.
7. **Maintainer dashboard** — for OSS repos: ranked queue of PRs by review priority, AI-likelihood, and stale time.

## Design direction

- **Tone is non-negotiable.** No condescending language. No emojis. Comments read like a senior engineer doing a thorough review on a Tuesday morning.
- **Optional, not pushy.** Default to "comment as a suggestion." Only block merges if explicitly configured.
- **Explainability everywhere.** Every flag has a "why this matters" expansion with the underlying rule and an example.
- **Maintainer mode != contributor mode.** Same tool, different defaults. Maintainers see triage views; contributors see educational reviews.

## Monetization

- **Per-seat:** $19/dev/mo on commercial repos.
- **Per-repo OSS plan:** $99/repo/mo for popular OSS projects whose maintainers want the maintainer dashboard. Free for repos under a low activity threshold.
- **Enterprise:** $40K+/yr — custom rule packs, on-prem GitHub Enterprise support, audit logs.

## Dependencies

- **Repo X-ray** at v1.0+ for convention checks and call-graph reasoning.
- **Shared platform** auth, billing, dashboard.
- **External:** GitHub App framework, LLM provider for nuanced rule evaluation (cached aggressively).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| CodeRabbit / Greptile out-features us | Compete on AI-failure specificity (their generality is our wedge) and provenance signals. |
| LLM cost per PR balloons | Tiered analysis — cheap rules first, expensive LLM checks only on diffs that warrant them. Cache by file hash. |
| False positives erode trust | Conservative thresholds at launch. Track per-customer FP rate; auto-tune rules over 30-day windows. |
| Maintainer adoption is hard to drive | Free tier for OSS, plus tight integration with TriageBot if that idea is later added (Wave 5+). |

## Future roadmap

- v1.1: PR-pair view — "this is the third near-duplicate PR for this feature; consolidate?"
- v1.2: convention learning — adapts rules to the repo's actual style instead of using global defaults.
- v1.3: cross-PR review — flags conflicts between two open PRs.
- v2.0: review-as-pair-programming — interactive review session with the contributor instead of static comments.

## Validation plan (30-day kill criteria)

- Pre-launch: 100+ design partner maintainer signups.
- Beta: average review-acceptance rate above 60% on bot suggestions across 10 design partners.
- Trial-to-paid conversion: 25%+ on commercial trials.
- Below 50% conversion or below 40% acceptance rate: iterate on tone and rule precision; don't kill yet — this is a quality problem, not a market problem.

## Built on (existing assets — biggest acceleration in the platform)

Three of Abdullah's existing GitHub Apps are essentially early prototypes of Agent-PR Reviewer's core. Lift-and-shape, do not rewrite:

- [`ai-quality-gate`](https://github.com/AbdullahBakir97/ai-quality-gate) — **direct lift**. AI-driven quality gate on every PR (readability, scope, risk scoring) is precisely Agent-PR Reviewer's MVP. Take the architecture, extend with AI-failure-mode detectors and Repo X-ray integration.
- [`pr-coach`](https://github.com/AbdullahBakir97/pr-coach) — coaching authors during review (title/description/scope feedback) is the **"reviewer assist mode"** feature in this spec. Pull the code in.
- [`commit-craft`](https://github.com/AbdullahBakir97/commit-craft) — conventional-commits formatting is a natural sub-feature. Merge as the **"commit normalization"** capability.

The GitHub App scaffolding, webhook handling, PR diff ingestion, and comment posting infrastructure are **already done across these three repos.** What remains is:

1. The AI-failure-mode detector pack (the actual differentiator).
2. Repo X-ray integration for convention checks.
3. Provenance scoring.
4. Maintainer dashboard.

**Estimated time saved in Wave 2: 4–6 weeks.** This is the single largest schedule acceleration in the entire DevTrust plan. With this head start, Agent-PR Reviewer is shippable in Wave 2 even without the full team expansion.

**Pre-Wave-2 task:** Audit the three repos for license compatibility, code quality, and test coverage. If they're recent prototypes rather than production-hardened, the lift is still worthwhile but the hardening work goes back into the schedule.
