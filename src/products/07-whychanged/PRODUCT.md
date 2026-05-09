# 07 — WhyChanged

> At incident time: "what changed in your service window?" with ranked culprits.

| | |
|---|---|
| **Lane** | Open source |
| **Wave** | 3 (months 6–9) |
| **Lead user** | SREs, on-call developers, application engineers |
| **License** | Apache-2.0 |
| **Monetizes via** | Hosted multi-team correlation SaaS ($79/team/mo) |

---

## Pain point

> *"My monitoring tells me there's a problem. It doesn't tell me what changed."*

Repeated complaint across r/devops, r/programming, and Hacker News. Production incidents cost 30+ minutes correlating recent deploys, feature-flag toggles, config drifts, and dependency updates by hand. Every team has reinvented this loop. Nobody has standardized it.

## Target user

- **Primary:** SREs and on-call engineers during incidents.
- **Secondary:** Engineering managers running blameless post-mortems.
- **Tertiary:** Teams without a dedicated SRE function — small companies where the on-call is also the developer who shipped the bug.

## Value proposition

*"Your changelog at incident time. Ranked. With one-click rollbacks."*

Demo line: **"Pinpoint the deploy that caused your incident in 30 seconds, not 30 minutes."**

## Key features (MVP)

1. **`whychanged init`** — connects to your deploy events (Vercel, Netlify, Render, ArgoCD, GitHub Actions deploys, custom webhooks), feature flag platform (LaunchDarkly, Statsig, Unleash, OpenFeature), config sources (Kubernetes, Doppler, Vault), and dependency sources (lockfile changes).
2. **Service-window correlation** — given a service name and a time window, returns a ranked list of changes. Ranking factors: time proximity, blast radius, history of similar past incidents.
3. **One-click rollback links** — for every ranked change, generates a deep link to the rollback action in the source system.
4. **Incident channel integration** — bot for Slack, Discord, Teams. Drop a service name in #incidents and WhyChanged replies with the ranked changelog.
5. **Post-mortem export** — markdown export of the timeline for the post-mortem doc.
6. **Repo X-ray correlation** (when both are present) — flags changes that touched code paths likely affected by the incident's symptom.

## Design direction

- **Calm during incidents.** No alarms, no red animations, no urgency theater. The product is read at 2am — make it readable.
- **30-second TTV (time-to-value).** From first install to "here's the change that broke prod" must take under 30 seconds with sample data.
- **Self-hosted-first, hosted-second.** Many teams won't put incident data into another vendor's cloud. Self-host is the lead.
- **Open data format.** Exports to JSON / NDJSON. Anyone can build on top of WhyChanged data.

## Monetization

- **OSS core is free forever.** Apache-2.0.
- **Hosted multi-team SaaS** — $79/team/mo. Aggregates incident data across all team services into one search surface; cross-team correlation ("your incident lines up with their deploy").
- **Enterprise** — $30K+/yr for SOC 2, audit logs, on-prem hosted variant, SSO.

## Dependencies

- **Optional:** Repo X-ray for code-level correlation.
- **Optional:** Agent Trace SDK for AI-agent-related incidents (when agents are part of the production path).
- **Shared platform:** only hosted variant uses shared infra.
- **External:** webhooks from deploy and feature flag platforms.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Datadog Watchdog or Honeycomb release a similar feature | Compete on cross-vendor integration depth (their features are vendor-locked) and the OSS path. |
| Self-hosting friction kills adoption | Single-binary install with built-in SQLite for storage. Optional Postgres for scale. |
| Integration matrix is a moving target | Ship the most popular 6 integrations on day 1 (GitHub Deploys, Vercel, Netlify, ArgoCD, LaunchDarkly, Statsig) and add at the rate of one per month after. |
| Quiet during quiet times — hard to demo | Synthetic incident scenario built in: `whychanged demo` runs a realistic example. |

## Future roadmap

- v1.1: anomaly-aware ranking — uses metric anomalies from Prometheus / Datadog to weight rankings.
- v1.2: cross-service blast-radius — "this change to service A also broke service B because they share dependency X."
- v1.3: change-quality scoring — passive scoring of every deploy on observed-incidents-per-deploy, surfaced in the dashboard.
- v2.0: predictive incident routing — when a high-risk change deploys, pre-page the right person.

## Validation plan (30-day kill criteria)

- 200+ self-hosted installs in 30 days (measurable via opt-in telemetry).
- 50+ Slack/Discord bot installs.
- HN front-page on launch (top 30).
- 100+ GitHub stars in 30 days.
- Below threshold: pivot to a hosted-only model with paid integrations as the primary funnel.

## Why this in Wave 3

Wave 3 opens the RUN product line. WhyChanged is the OSS hook — the "free thing every SRE will install in an afternoon" — that makes the rest of the RUN line credible. TokenCost (the paid Wave 3 product) lands behind it.
