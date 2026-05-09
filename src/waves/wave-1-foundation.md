# Wave 1 — Foundation + lead bet

**Months 0–3 · "Earn an audience. Earn first revenue."**

---

## What ships

| Product | Lane | Goal by end of wave |
|---|---|---|
| Repo X-ray | OSS · foundation | v0.5 public release, 1K GitHub stars, 50 paid hosted-tier signups |
| Smart Test Selector | Paid · lead bet | Closed beta → public launch, 5 paying design partners, $5K MRR |
| Shared platform infra | Internal | Auth, billing, UI shell, agent runtime stub all live |

## Why this order matters

Repo X-ray ships first because two later products consume it. Smart Test Selector lands one week after Repo X-ray's public release so its first version can already use the call graph and conventions data. Shared platform infrastructure is built in parallel during the first 3 weeks so neither product has to build its own auth or billing.

## Week-by-week

### Weeks 1–3 — Setup and scaffolding

- Land org, registered company, domain, Stripe account, Clerk auth, Vercel/Render/Fly.io deploy target.
- Build shared platform v0: auth, basic billing, UI shell, deploy pipeline.
- Repo X-ray v0.1 prototype — single-language (TypeScript) call graph + entry-point detection.
- Smart Test Selector landing page live; waitlist open.

### Weeks 4–6 — Repo X-ray validation and v0.3

- Run 30-day validation playbook on Repo X-ray.
- Add Python and Go support.
- Add the markdown-companion artifact and MCP server.
- Open public GitHub repo (Apache-2.0).

### Weeks 7–9 — Smart Test Selector closed beta

- Sign 5 design partners.
- Build the GitHub App.
- Wire test-selection logic to Repo X-ray's call graph.
- Daily product calls with design partners.

### Weeks 10–12 — Public launches

- Repo X-ray v0.5 launches publicly (HN post, blog post, Mastodon, dev.to).
- Smart Test Selector public beta opens.
- First public pricing page goes live for Smart Test Selector.

## Success criteria

- 1K+ GitHub stars on Repo X-ray.
- 5 paying customers on Smart Test Selector ($300+/mo each).
- Shared platform supports both products without per-product hacks.
- 1 HN front-page post (top 30) for either product.

## Kill criteria

- Repo X-ray < 100 stars after 30 days post-launch → re-evaluate product (the foundation is wrong, not just the marketing).
- Smart Test Selector < 50 waitlist signups after landing page launch → reposition or substitute Agent-PR Reviewer as lead bet.
- Shared platform takes more than 4 weeks of build time → cut scope (auth + billing only; build dashboard module-by-module instead of as a shell).

## Headcount and resources

- 1 founder/principal engineer (Abdullah).
- 1 contractor for design / branding (3 weeks part-time, weeks 4–6).
- Tools budget: ~$200/mo for hosting, services, tooling.
- Marketing budget: $0 — all distribution is organic.

## GTM activities

- Build-in-public posts on X / Mastodon / Bluesky 3× per week.
- One technical blog post per fortnight on the engineering problem (not the product).
- Submit Repo X-ray to: Awesome lists, Reddit r/programming weekly thread, dev.to, Hacker News (when v0.5 ships).
- One conference CFP submitted by week 12 (target: an OSS / DevOps conference 6 months out).

## Hand-off to Wave 2

By end of Wave 1, the Wave 2 prerequisites must be true:

- Repo X-ray v0.5+ stable enough to consume in production.
- Shared platform infrastructure mature enough that adding Wave 2 products is a pure feature build, not a re-architecture.
- 1+ paying customer on Smart Test Selector signals product-market signal worth doubling down on.
- Decision: "go for Wave 2" or "another month on Wave 1 hardening" — explicitly answer this on day 84.
