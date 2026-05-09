# 06 — Agent Trace SDK

> Open standard for AI agent telemetry — OpenTelemetry for agents.

| | |
|---|---|
| **Lane** | Open source · foundation |
| **Wave** | 3 (months 6–9) |
| **Lead user** | Engineering teams running AI agents in production |
| **License** | Apache-2.0 |
| **Powers** | WhyChanged · TokenCost · AgentGuard |

---

## Pain point

Every agent observability vendor has its own format. OpenTelemetry semantic conventions for GenAI exist but are immature. Teams adopting Helicone, Langfuse, Phoenix, or LangSmith get locked into a vendor — and the moment they switch frameworks (LangChain → CrewAI → custom), the trace fidelity drops.

The Datadog 2026 State of AI Engineering report found 5% of all LLM call spans returned an error in February 2026 — 60% of those due to rate limits. That's millions of errors monthly that traditional APM tools either miss or misclassify because they don't speak agent.

## Target user

- **Primary:** Application developers and platform engineers running AI agents in production.
- **Secondary:** Vendors building observability tools who want a neutral standard to support.
- **Tertiary:** Other DevTrust products — WhyChanged, TokenCost, and AgentGuard all consume Agent Trace SDK output.

## Value proposition

*"One trace format. Every agent framework. Every observability vendor."*

Demo line: **"Switch from LangChain to your own agent in two days — your dashboards keep working."**

## Key features (MVP)

1. **TypeScript and Python SDKs** — one-line install, zero-config defaults. `@devtrust/trace` exports a `traced()` wrapper for any agent function.
2. **Structured spans for the right things** — prompt, model call, tool call, tool result, planning step, retry, fallback, human-in-the-loop boundary, parent-child relationships.
3. **OTel-compatible** — emits as OpenTelemetry spans with extended `gen_ai.*` semantic conventions. Existing OTel pipelines just work.
4. **Reference exporters** — to Datadog, Honeycomb, Grafana, ClickHouse, Langfuse-compatible format, plain JSON files.
5. **Self-hostable viewer** — `agent-trace ui` opens a web UI like Jaeger but for agent traces — see the full reasoning tree, click to inspect prompts, replay from any step.
6. **Framework adapters** — official adapters for LangChain, LangGraph, CrewAI, Microsoft Agent Framework, OpenAI Agents SDK, Vercel AI SDK, Mastra, Anthropic SDK, Mastra.

## Design direction

- **Spec-first.** Publish the trace schema as a versioned, openly governed spec before shipping the SDK. Invite competitor vendors to support it.
- **Zero-friction adoption.** A developer should be able to instrument their agent in under 5 minutes and see a meaningful trace.
- **Beautiful default viewer.** The hosted UI should make people want to instrument more, not less.
- **Privacy-respecting defaults.** PII redaction is on by default (configurable); prompts can be hashed and not stored.

## Monetization

- **OSS core is free forever.** Apache-2.0.
- **Hosted ingest + storage** — $0.50 per million tokens of trace volume. Generous free tier (10M tokens/mo).
- **Enterprise** — $50K+/yr for SSO, multi-region storage, on-prem viewer, retention policies.

## Dependencies

- **Foundation:** none — Agent Trace SDK is itself a foundation for the RUN line.
- **Shared platform:** only the hosted variant uses shared infra.
- **External:** OpenTelemetry semantic conventions for GenAI (we extend, don't replace), Apache Arrow (efficient export format).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| OpenTelemetry GenAI conventions stabilize and absorb our extensions | Treat this as the goal, not the failure. Govern openly so our work feeds into the standard. |
| Big vendors (Datadog, Langfuse, Honeycomb) ignore us | Start by supporting their formats as exporters — make adoption a one-line addition for their existing customers, not a switch. |
| Framework adapters drift behind upstream changes | Automated nightly tests against framework `main` branches. Public dashboard showing adapter status. |
| Hosted ingest pricing race-to-zero | Differentiate on viewer quality and replay capability, not raw storage. |

## Future roadmap

- v1.1: trace-driven evals — define eval cases as "this trace shape must always succeed" instead of input/output pairs.
- v1.2: multi-agent traces — proper visualization of agent-to-agent communication.
- v1.3: cost-aware spans — real-time token cost per span, surfaced inline in the viewer.
- v2.0: distributed agent debugging — time-travel debugging across multiple agents in the same workflow.

## Validation plan (60-day kill criteria — longer because foundation work)

- 1K+ GitHub stars in first 60 days post-launch.
- 3 framework adoptions of the format (we can implement these ourselves but ideally upstream picks them up).
- 5 production users emit >10M spans/mo via the SDK by day 90.
- Below threshold: reposition as a SaaS-only product (don't try to win as a standard).

## Why this is the foundation, not a feature

If Agent Trace SDK exists, then WhyChanged becomes "correlate deploys to incidents using shared spans." TokenCost becomes "aggregate cost from spans by tag." AgentGuard becomes "evaluate policies against spans in real time." Three products' worth of telemetry plumbing, written once.
