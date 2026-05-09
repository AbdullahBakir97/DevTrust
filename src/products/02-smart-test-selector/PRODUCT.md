# 02 — Smart Test Selector

> Decides which tests must run on each PR. Cuts CI from 28→9 min.

| | |
|---|---|
| **Lane** | Paid SaaS · Wave 1 lead bet |
| **Wave** | 1 (months 0–3) |
| **Lead user** | Engineering managers |
| **Pricing** | $10/dev/mo, billed annually. Free tier for OSS repos. |
| **Depends on** | Repo X-ray · Shared platform infrastructure |

---

## Pain point

CI pipelines run every test on every PR because nobody trusts "affected tests" detection. The cost is brutal: 30+ minute builds, devs context-switching while waiting, accumulated CI bills running tens of thousands monthly for mid-size teams.

A developer on Hacker News literally asked for this verbatim:

> *"An LLM tool that sits on a CI pipeline and proposes which tests should be blocking — analyzing changes and selecting the relevant test suites instead of brute-force running everything. And estimating how many times to run new tests to verify they aren't flaky."*

## Target user

- **Primary buyer:** Engineering managers and platform leads at companies with 20+ engineers and a CI bill over $2K/month.
- **Primary user:** Every developer on the team, indirectly — they see faster green/red feedback on their PRs.
- **Secondary buyer:** CTOs at high-growth startups who care about engineer velocity.

## Value proposition

*"Stop running 100% of tests on 100% of PRs. We pick the 20% that matter, plus catch flaky new tests before they merge."*

Demo line: **"Acme Corp cut CI from 28 minutes to 9 minutes — and shipped 3× more PRs per engineer per week."**

## Key features (MVP, by end of Wave 1)

1. **GitHub App** — installs with one click, requires read access to repo and PR comments, write access to PR checks.
2. **Diff-aware test selection** — on each PR, analyzes the diff using Repo X-ray's call graph and dependency map, ranks tests by likelihood of being affected.
3. **Three-bucket output** — `must run` (will likely fail if there's a regression) · `should run` (touched indirectly) · `safe to skip` (no dependency path).
4. **PR check integration** — adds a "Smart Test Selector" check that runs only the `must` and `should` buckets. Falls back to full suite on first run or when confidence is low.
5. **Flakiness prediction** — for new tests, runs them N times in a sandbox before merge and reports the flakiness probability.
6. **Auditability** — PR comment shows the reasoning: "Skipped 247 tests because no path from your changes touches them. Here are the top 5 if you disagree."
7. **CI minute report** — weekly digest: "Saved 412 hours of CI this week."

## Design direction

- **Trust through transparency.** Every "skipped" test must have a one-click "show me why" expansion. No black box.
- **Override is a first-class action.** Developers can request "run all anyway" with one click; Smart Test Selector learns from these overrides.
- **Color-blind friendly traffic light** — green / amber / grey, with patterns and text labels, not just color.
- **CLI parity.** Everything the GitHub App does is also a CLI command (`sts select`, `sts predict-flake`) for self-hosted CI.

## Monetization

- **$10/dev/mo, annual billing** — straightforward per-seat pricing matched to GitHub seat counts.
- **Free for OSS repos** — distribution play; OSS adoption drives mindshare.
- **Enterprise** ($30K+/yr) — SAML SSO, audit logs, on-prem GitHub support, monorepo-scale optimizations.

ROI math for buyer: typical mid-size team spends $5–10K/mo on CI. A 50% cut at $10/dev/mo for 30 devs = $300/mo cost vs. $2.5–5K/mo savings. Payback in week 1.

## Dependencies

- **Repo X-ray must be at v0.5+ before Smart Test Selector v1 ships.** Specifically: stable call graph and dependency export.
- **Shared platform:** auth, billing, dashboard.
- **External:** GitHub App framework (Probot or Octokit), CI runner integration (GitHub Actions, CircleCI, Buildkite, Jenkins).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| GitHub ships native Test Selector via Copilot Workspace | Beat them on cross-CI support, transparency, and flakiness prediction. Their feature will be GitHub-only. |
| Customers don't trust "skipped" tests | Conservative defaults: bias toward "should run" over "skip". Show savings monthly so trust accumulates. |
| Repo X-ray takes longer than expected to ship | Smart Test Selector ships a slimmer v0.1 using only Git diff + simple heuristics. Upgrades when Repo X-ray is ready. |
| Flakiness predictor false positives | Start with prediction-only mode (just shows the score, doesn't block merges). Block only after 3 months of accuracy data. |

## Future roadmap (post-Wave 1)

- v1.1: priority-aware ordering — "run the 5 tests most likely to fail first, fail-fast the build."
- v1.2: cross-PR insight — "this PR breaks tests that are flaky on `main` already."
- v1.3: language coverage — extend beyond JS/TS/Python/Go to Java, C#, Ruby.
- v1.4: monorepo turborepo / Nx integration.
- v2.0: predictive build cancellation — kill builds that are 95%+ certain to fail before they finish.

## Validation plan (30-day kill criteria)

- 50+ engineering managers on the waitlist within 30 days of landing page launch.
- 5 design partners committed to a 30-day trial.
- After trial: at least 3 of 5 sign annual contracts. If 0, kill.
- Demoed savings of >40% CI time on at least 1 design partner repo. If <20%, the value prop is fake.

## Why this is the Wave 1 lead bet

Measurable ROI in dollars (CI minutes), undeniable demo ("28 → 9 min"), repo-specific learning that compounds over time, and a developer literally asking for it on HN. Of the 9 DevTrust products, this is the one most likely to generate revenue inside 90 days.
