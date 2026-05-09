---
name: ship-checklist
description: Pre-launch checklist for a DevTrust product about to go public
arguments:
  - name: product
    description: Which product is shipping
    required: true
---

# /ship-checklist <product>

Generate a pre-launch checklist tailored to the lane the product is in:

For **OSS lane** products (Repo X-ray, CI Local, Agent Trace SDK, WhyChanged):
- README is complete with install, quickstart, common usage
- LICENSE file present (Apache-2.0 unless noted)
- CONTRIBUTING.md and CODE_OF_CONDUCT.md present
- Issue templates and PR template configured
- v0.1.0 tagged and changelog written
- Landing page or docs site live
- Launch post drafted (Hacker News, X / Mastodon, dev.to, the relevant subreddits)
- Demo video or asciicast recorded
- "Awesome list" submissions queued

For **paid lane** products (Smart Test Selector, Agent-PR Reviewer, Dep Upgrade Pilot, TokenCost, AgentGuard):
- All of the above (where applicable) PLUS:
- Stripe billing wired and tested with a test card
- Auth provider integrated (Clerk / Auth.js / WorkOS)
- Pricing page live with clear tiers
- 5+ paying design partners onboarded
- SLA, ToS, Privacy Policy reviewed
- Status page set up (e.g. statuspage.io)
- Customer-facing changelog committed to weekly cadence
- Onboarding email sequence written
- Crash reporting and product analytics installed

After producing the checklist, fetch the product's current state from `products/NN-name/PRODUCT.md` and tick off any items that are clearly already done. Output as a markdown task list.
