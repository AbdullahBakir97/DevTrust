# 05 — Dep Upgrade Pilot

> AI agent that proposes safe dependency upgrade paths and drafts the PRs.

| | |
|---|---|
| **Lane** | Paid SaaS |
| **Wave** | 4 (months 9–12) |
| **Lead user** | Platform engineers, security teams, EU CRA-affected orgs |
| **Pricing** | $79/repo/mo · Enterprise from $40K/yr |
| **Depends on** | Repo X-ray · Shared platform |

---

## Pain point

Renovate and Dependabot are mechanical: they create PRs that bump versions and let humans figure out the rest. Most teams have hundreds of these PRs sitting open for months. When the EU Cyber Resilience Act starts biting in late 2026, "we'll get to it" stops being an acceptable answer — companies that ship software in the EU need an auditable trail of dependency hygiene.

55% of organizations that failed a 2025 compliance audit had end-of-life OSS dependencies in their stacks.

## Target user

- **Primary:** Platform engineering teams at companies with 50+ services.
- **Secondary:** Security and compliance teams at companies that ship software into the EU.
- **Tertiary:** Solo maintainers of large OSS projects who want to stay current without losing weekends.

## Value proposition

*"Your dependencies, upgraded — safely, with the test runs to prove it, in priority order driven by risk."*

Demo line: **"Reduced EOL packages from 47 to 3 in 6 weeks, with a CRA-ready audit trail."**

## Key features (MVP)

1. **Risk-prioritized upgrade plan** — daily scan produces a queue ordered by CVE severity, EOL status, and breaking-change probability.
2. **Safe-path proposals** — for each upgrade, the agent reads release notes and changelog, identifies breaking changes, searches the codebase via Repo X-ray for affected call sites, and drafts a PR with the necessary code changes.
3. **Test-driven verification** — runs the test suite against the upgrade, reports what broke and why. Won't open the PR if the regression rate is high.
4. **Three-tier PR templates** — `safe upgrade` (fully automated), `assisted upgrade` (PR with todo comments where human judgment is needed), `risky upgrade` (analysis only, no PR; for human pickup).
5. **CRA-ready audit log** — every upgrade decision and skipped upgrade is logged with reasoning, satisfying compliance evidence requirements.
6. **EOL early-warning** — flags packages 90 days before they hit EOL with a suggested replacement.

## Design direction

- **Conservative by default.** A failed upgrade is worse than a missed one. The agent should propose `--dry-run` first, get sign-off, then execute.
- **Compliance language is first-class.** UI surfaces "CRA Article X compliance" labels where applicable; the audit log is exportable as a compliance-ready report.
- **Calm UI.** This is a stress-relieving product, not a hype product. Cool palette, low-contrast accents, plain language.

## Monetization

- **Per-repo:** $79/repo/mo (the most actively touched repos justify the spend).
- **Per-org annual:** $40K+ for org-wide rollouts with SSO, custom risk policies, and dedicated CRA reporting.
- **CRA Compliance Bundle:** $100K+/yr — adds dedicated audit support during enforcement actions, expert review of risk policies.

## Dependencies

- **Repo X-ray** for call-site analysis (which functions actually use the dependency being upgraded).
- **Shared platform** auth, billing, dashboard.
- **External:** Renovate / Dependabot (we're a layer above, not a replacement), the GitHub Advisory Database, OSV, EOL.date, package-manager-specific tooling for changelog parsing.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Renovate / Dependabot ship native risk-prioritization | We layer above with the agent's safe-path proposals — they don't write code, we do. |
| LLM cost per PR is too high to be profitable at $79/mo | Aggressive caching of changelog analysis; cheap heuristics first, expensive LLM checks only when stakes warrant. |
| EU CRA enforcement is delayed, killing the urgency | Reposition as a security/SRE product. The compliance angle is one of three buyer profiles, not the only one. |
| Customers don't trust the agent to write upgrade code | Default to `assisted` mode (PR with TODO comments) for first 90 days. Promote to `safe` only after track record. |

## Future roadmap

- v1.1: language coverage — extend beyond JS/TS, Python, Go, Rust to Java (Maven/Gradle), C# (NuGet), Ruby (Bundler), PHP (Composer).
- v1.2: cross-repo coordination — when a shared dep upgrades, coordinate the PR across all consuming services.
- v1.3: SBOM generation in CycloneDX and SPDX, exportable for any compliance regime.
- v2.0: upstream contribution — when we hit a breaking change with no clear migration, file a PR with the affected library suggesting a deprecation shim.

## Validation plan (30-day kill criteria)

- 10 design partners committed before Wave 4 begins (line of sight from Wave 3 launches).
- After 30 days of beta: average upgrade success rate above 70%; trial-to-paid conversion above 30%.
- If conversion is under 15% even with strong success rate: it's a "nice-to-have" product, not a "must-buy" — re-position around CRA compliance specifically.

## Why this in Wave 4

Compliance products sell to enterprises after credibility is established. By Wave 4, DevTrust has 4 OSS launches and 3 paid products live — that's the credibility platform an enterprise sales motion can stand on. Earlier in the waves, this product wouldn't get past procurement.
