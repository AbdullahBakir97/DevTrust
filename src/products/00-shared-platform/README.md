# 00 — Shared platform infrastructure

The four pieces of infrastructure that every DevTrust product reuses. Built once in Wave 1 (alongside Repo X-ray and Smart Test Selector). Owned by a single internal codebase, exposed to each product via a small SDK.

---

## What's shared

### 1. Auth & teams

- Single sign-on (Google, GitHub, Microsoft) for every product.
- Workspace / team accounts with role-based access (Owner, Admin, Member, Viewer).
- Audit log captured for every privileged action across all 9 products.
- One-click invite flows reused across products.

**Build vs. buy:** Buy. Use Clerk or WorkOS — auth is not where DevTrust differentiates.

### 2. Billing & usage

- Single Stripe account, single billing surface — customers see one invoice covering whatever DevTrust products they use.
- Per-seat, per-usage, and per-tracked-spend models all supported (different products use different ones).
- Usage metering pipeline: every product emits standardized events; billing rolls them up nightly.
- Self-serve upgrade and downgrade flows.

**Build vs. buy:** Buy the substrate (Stripe), build the metering layer (it's a small Node service).

### 3. Agent runtime

- Shared LLM ops layer — model routing (OpenAI / Anthropic / Bedrock / open models), retry, fallback, structured output enforcement, prompt caching.
- One place to update model versions across all products that use AI.
- Per-tenant rate limits and cost ceilings.
- Reuses Agent Trace SDK (which exists by Wave 3) for observability — until then, simple structured logging.

**Build vs. buy:** Build a thin layer (under 1000 lines). Don't adopt LangChain or LangGraph — too heavy for what DevTrust needs.

**Existing asset:** Abdullah's [`cortex`](https://github.com/AbdullahBakir97/cortex) repo — *"Memory-augmented agent kernel — context windows, retrieval, and structured output for LLM workflows"* — is a strong candidate as the starting point for `@devtrust/runtime`. It already implements the three things the runtime needs (memory, retrieval, structured output). Audit it pre-Wave-1 to confirm production readiness; if good, save 1–2 weeks vs. greenfield.

### 4. Unified dashboard

- One web app at `app.devtrust.dev` with sidebar navigation across all products the user has access to.
- Each product is a "module" rendered in the same shell.
- Shared components (table, chart, filter bar, settings panel) used everywhere.
- Themed by product family (SHIP = warm orange-grey palette; RUN = cool blue palette) but visually consistent.

**Build vs. buy:** Build. UI consistency is part of the customer promise.

---

## What this means for individual products

Each product spec in the sibling folders **does not** re-describe auth, billing, or the dashboard shell. It only describes the product-specific module. When implementing, every product imports `@devtrust/auth`, `@devtrust/billing`, `@devtrust/runtime`, and `@devtrust/ui-shell` and focuses its code on its unique value.

This is the single biggest reason DevTrust is built as one platform instead of 8 separate startups: **about 60% of the typical SaaS plumbing is shared.**

## Wave 1 scope for shared platform

- Auth (Clerk integration) — Week 1
- Billing (Stripe + metering) — Week 2
- UI shell (Next.js + Tailwind + shadcn/ui) — Week 2-3
- Agent runtime stub (just OpenAI + Anthropic + retry) — Week 3
- Deploy target (Vercel + Neon Postgres + Upstash Redis) — Week 1

By end of Wave 1, the shared platform supports Repo X-ray (OSS, talks to platform for hosted variant only) and Smart Test Selector (paid, fully on platform).
