# Wave 3 — Open the RUN line

**Months 6–9 · "New foundation. New product line. New buyer."**

---

## What ships

| Product | Lane | Goal by end of wave |
|---|---|---|
| Agent Trace SDK | OSS · foundation | v0.5 public release, 3 framework adoptions, 10K GitHub stars |
| WhyChanged | OSS | v1.0 public launch, 200+ self-hosted installs, 50+ Slack/Discord bot installs |
| TokenCost | Paid SaaS | Public launch, 50+ free-tier teams, 5+ paid teams |

This is the busiest wave (3 products). It opens the RUN product line and its second foundational primitive. Bandwidth is the biggest risk.

## Why this order matters

Agent Trace SDK ships **first** in the wave because the other two RUN products consume it. WhyChanged and TokenCost can technically run without it (using narrower data sources) but the platform thesis breaks if Wave 3 ships them as standalone products. Agent Trace SDK has to be at v0.3+ before TokenCost goes to closed beta.

## Month-by-month

### Month 7

- Agent Trace SDK v0.1 — TypeScript and Python SDKs, OTel-compatible spans, exporters to Datadog and ClickHouse.
- WhyChanged v0.5 closed beta with 5 SREs.
- TokenCost v0.1 closed beta with 3 design partners (one of whom must be a finance contact, not just engineering).
- Smart Test Selector and Agent-PR Reviewer continue scaling — no new feature development beyond bug fixes.

### Month 8

- Agent Trace SDK v0.3 — framework adapters for LangChain, CrewAI, Vercel AI SDK.
- Agent Trace SDK self-hostable viewer ships.
- WhyChanged public launch.
- TokenCost public beta — pricing page live, free tier auto-onboarding.

### Month 9

- Agent Trace SDK v0.5 launch (HN, conference talk, dev.to).
- WhyChanged v1.0 launch with deploy-platform partnership posts (Vercel, Render, Fly.io).
- TokenCost GA launch with finance-audience content (LinkedIn posts targeting CFOs/VP Finance).
- Wave 3 retrospective and Wave 4 sales motion design.

## Success criteria

- Combined MRR (4 paid products: STS, Agent-PR Reviewer, plus the new TokenCost) > $40K.
- Agent Trace SDK: 10K+ stars, 3+ frameworks adopted the format.
- WhyChanged: top 30 on HN at launch.
- TokenCost: 5+ paying customers including 1 enterprise lead in pipeline.

## Kill criteria

- Agent Trace SDK fails to attract framework adoption (any of LangChain, CrewAI, Vercel AI SDK) → reposition as a SaaS-only product in Wave 4.
- WhyChanged < 100 self-hosted installs in 30 days → keep as a free utility but stop promoting; cut hosted variant.
- TokenCost trial-to-paid conversion < 10% → likely a positioning issue (too engineering, not enough finance). Pivot the landing page; don't kill before re-test.

## Headcount and resources

- 2–3 engineers (founder + 1–2 hires/contractors).
- 1 part-time content / GTM hire — needed because we now sell to finance buyers, not just engineering.
- Tools budget: $1K/mo.
- Marketing budget: $3K/mo (LinkedIn ads for TokenCost finance audience, sponsorships for SRE-focused podcasts/newsletters for WhyChanged).

## GTM activities

- **Two distinct go-to-market motions** for the first time:
  - SHIP-line GTM (developer-led, OSS-driven, dev-tool blogs and HN). Continue the Wave 1–2 playbook.
  - RUN-line GTM (mix of developer for WhyChanged and finance/exec for TokenCost). New surfaces: LinkedIn, finance-leader newsletters, CFO Slack groups.
- **Cross-product offers:** "Buy Smart Test Selector + TokenCost together for 20% off" — start to prove the platform thesis with packaged deals.
- **Compliance positioning groundwork:** publish "OWASP Top-10 for Agentic Apps — what every AI engineer should know" content to set up Wave 4 AgentGuard launch.

## Hand-off to Wave 4

By end of Wave 3, Wave 4 prerequisites must be in place:

- 5 design partners committed for AgentGuard — outreach started in month 8.
- Compliance / SOC 2 Type 1 process started for our own platform (12 weeks lead time minimum).
- Decision: do we bring on a sales hire for Wave 4, or stay founder-led? Answer this on day 252.
- Decision: which Wave-4 product launches first — Dep Upgrade Pilot or AgentGuard? Default order is AgentGuard first (compliance window is closing) but pipeline data may flip this.
