# Wave 2 — Expand SHIP

**Months 3–6 · "Two more SHIP products. Reuse everything."**

---

## What ships

| Product | Lane | Goal by end of wave |
|---|---|---|
| Agent-PR Reviewer | Paid SaaS | Public launch, 10 paying teams, $15K MRR |
| CI Local | OSS | Public launch, 5K GitHub stars, 1K daily active users |

By end of Wave 2: SHIP product line has 4 of its 5 products live. Smart Test Selector should be at $20K+ MRR (5× growth from Wave 1's $5K). Repo X-ray should be at 5K+ stars.

## Why this order matters

Agent-PR Reviewer reuses Repo X-ray (no new foundation work). CI Local is the **OSS distribution win** that drives top-of-funnel for both paid Wave-1 and Wave-2 products. Without a viral OSS launch in Wave 2, the SHIP line doesn't have enough top-of-funnel for the rest of the year.

## Month-by-month

### Month 4

- Agent-PR Reviewer closed beta with 10 design partners (mix of commercial teams and OSS maintainers).
- CI Local v0.1 prototype — GitHub Actions workflow runner, Linux only.
- Smart Test Selector v1.1 — flakiness predictor goes from beta to GA.
- Begin pricing experimentation on Smart Test Selector ($10/seat is the placeholder; test $7, $10, $15).

### Month 5

- Agent-PR Reviewer public beta launch.
- CI Local v0.3 — GitLab CI and CircleCI support added.
- Begin running paid ads experiment on Smart Test Selector — small budget ($500/mo) for 30 days as a learning, not a growth, exercise.

### Month 6

- Agent-PR Reviewer GA launch with public pricing page.
- CI Local v1.0 launch — HN post, Awesome list submissions, dev.to, conference CFP follow-up.
- Wave 2 retrospective and Wave 3 kickoff prep (last 2 weeks).

## Success criteria

- Agent-PR Reviewer: 10+ paying teams.
- CI Local: 5K+ stars, ranked in top 30 on a Hacker News front page.
- Combined MRR (Smart Test Selector + Agent-PR Reviewer) > $20K.
- Cumulative GitHub stars across DevTrust OSS products > 10K.

## Kill criteria

- Agent-PR Reviewer trial-to-paid conversion below 15% → tone or rule-quality problem; iterate, don't kill outright.
- CI Local under 1K stars after 30 days post-launch → kill the "category leader" framing; reposition as a focused indie tool.
- If Smart Test Selector growth flatlines (<2× from Wave 1) → halt Wave 2 expansion and double-down on Smart Test Selector marketing for one month.

## Headcount and resources

- 1 founder/principal engineer.
- 1 part-time engineer added in month 4 (could be contractor or first hire) — primarily on CI Local.
- Tools budget: ~$500/mo (more hosting, more LLM calls, observability).
- Marketing budget: $1K/mo total.

## GTM activities

- Conference talk delivered (the one CFPed in Wave 1).
- Two technical blog posts per fortnight — one per product line.
- CI Local launch: dedicated launch sequence — 14 days of teaser content, launch day blast, 7 days of follow-up case studies.
- Begin building dependency-relationship between products — landing pages cross-link, "if you use X, you'll like Y" prompts in the dashboard.

## Hand-off to Wave 3

By end of Wave 2, Wave 3 prerequisites must be in place:

- Agent Trace SDK design spec drafted (we don't ship code in Wave 2, but the schema and the framework adapter list must be ready).
- Wave 3 design partners pre-identified — start outreach to teams running production AI agents in month 6.
- Bandwidth check: is the team large enough to ship 3 products in Wave 3? If not, push WhyChanged to Wave 4 and keep the wave to 2 products.
