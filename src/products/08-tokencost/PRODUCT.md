# 08 — TokenCost

> CFO-grade attribution of LLM spend by feature, team, and customer.

| | |
|---|---|
| **Lane** | Paid SaaS |
| **Wave** | 3 (months 6–9) |
| **Lead user** | Engineering leads, finance, FP&A, CFOs |
| **Pricing** | Free up to $1K tracked spend/mo · 1.5% of tracked spend (capped) · Enterprise $30K+/yr |
| **Depends on** | Agent Trace SDK · Shared platform |

---

## Pain point

CFOs ask engineering: *"What did our AI features cost last month, by feature, by team, by customer cohort?"* — and engineering can't answer cleanly. Per-token billing has made model cost a 2–3× quarterly variance line item that finance teams are rebuilding spreadsheets for every month.

Helicone, Langfuse, OpenMeter, and Vercel's AI SDK touch this. None have made it boardroom-grade.

## Target user

- **Primary buyer:** VP Engineering or CTO who has to defend AI budget to the CFO.
- **Primary user:** Engineering managers who want to know which feature cost the most this week.
- **Secondary:** FP&A and finance teams who need a number for the budget cycle.
- **Tertiary:** Heads of Product who need per-feature unit economics.

## Value proposition

*"AI costs explained to your CFO. By feature. By team. By customer. Forecasted, not just historical."*

Demo line: **"Budget alert: Feature X cost +127% this week. Two prompts to look at. Click to investigate."**

## Key features (MVP)

1. **One-line install** — drops in front of OpenAI / Anthropic / Bedrock / Vertex / Mistral / xAI clients. Tag every call automatically.
2. **Feature-, team-, customer-tagged dashboards** — slice the spend by any tag. Compare to last month, last quarter, budget.
3. **Budget alerts** — set per-feature monthly budgets; get Slack pings at 50%, 80%, 100%.
4. **Prompt-level cost diff on PR** — when a PR changes a prompt, post a comment estimating the per-request cost change.
5. **Forecasting** — "at current trajectory, you will exceed your monthly budget on day 23." Simple linear and seasonal models.
6. **CFO-ready exports** — monthly PDF report with executive summary, per-feature breakdown, variance commentary, and a finance-friendly summary tab.
7. **Customer-cost attribution** — for B2B SaaS using AI features, attribute model spend back to specific customer accounts. Crucial for unit economics on AI features.

## Design direction

- **Numbers, not narrative.** This is a finance product wearing engineering clothes. Tables and waterfalls win, prose loses.
- **Boardroom-grade defaults.** A CFO seeing the monthly PDF on Day 1 should not need to ask "what does this number mean?"
- **Two color palettes.** Cool blue / grey for finance audience; product-style orange / accent for engineering audience. Toggle at the dashboard level.
- **Invariant-checked.** Numbers reconcile across views. If the per-feature view says $X and the per-team view sums to $Y, they must be within rounding of each other. Build invariants as tests.

## Monetization

- **Free up to $1K tracked spend/mo** — generous because data depth is the moat; we want lots of teams emitting data.
- **Pay-as-you-go** — 1.5% of tracked spend, capped at $5K/mo for self-serve.
- **Enterprise** — $30K+/yr for SAML, audit logs, finance-system integrations (NetSuite, QuickBooks, Sage Intacct), private deployment.

ROI math for the buyer: a typical team spending $20K/mo on AI gets per-feature attribution and budget controls for $300/mo. Single avoided 2× quarter spike pays back the entire annual cost.

## Dependencies

- **Agent Trace SDK** at v1.0+ — TokenCost is fundamentally a tagged-aggregation view over Agent Trace data.
- **Shared platform** auth, billing, dashboard.
- **External:** finance-system integrations (NetSuite, QuickBooks).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Helicone or Langfuse adds CFO-grade reporting | Beat them on three fronts: invariant-checked numbers, finance-system integrations, customer-cost attribution. They're built for engineers; we're built for engineers' bosses. |
| Token prices keep dropping, our 1.5% take dries up | Move to per-seat pricing for finance team users in Year 2. Customer-cost attribution remains valuable regardless of token prices. |
| Customers don't want to pipe spend data to a vendor | Offer self-hosted tier in Year 2. Self-host doesn't get hosted forecasting but gets all dashboards. |
| Tagging discipline is hard to enforce | Provide a `requireTags()` middleware that fails fast if a tag is missing — make untagged calls a build-time error. |

## Future roadmap

- v1.1: cost-aware retrieval — show which retrievals over-fetch and suggest reductions.
- v1.2: model-routing recommendations — "switching this feature from GPT-4 to Claude Haiku saves $X/mo at <2% quality drop."
- v1.3: customer-pricing assistant — "your top 5 customers cost more than they pay; here's the price increase to recommend."
- v2.0: AI-feature P&L — tracks revenue and cost together for true per-feature unit economics.

## Validation plan (30-day kill criteria)

- 50+ teams installed (free tier) in 30 days.
- 5+ paying customers above $200/mo by day 60.
- 1+ enterprise contract signed by day 90.
- If under 30 free signups in 30 days, the positioning is wrong (most likely angled too "engineering" instead of "finance"). Pivot the landing page and try again.

## Why this in Wave 3

Wave 3 introduces the RUN product line, and TokenCost is the wave's revenue engine. WhyChanged earns OSS audience; Agent Trace SDK becomes the standard; TokenCost takes that audience and converts the CFO buyer.
