# 09 — AgentGuard

> Policy-as-code runtime for AI agents. Audit log + hard-no enforcement.

| | |
|---|---|
| **Lane** | Paid SaaS · Enterprise |
| **Wave** | 4 (months 9–12+) |
| **Lead user** | CISOs, platform leads, compliance teams |
| **Pricing** | $99/agent/mo standard · Enterprise from $30K/yr · SOC 2 Compliance Bundle from $80K/yr |
| **Depends on** | Agent Trace SDK · Shared platform |

---

## Pain point

OWASP published a Top 10 for Agentic Applications in December 2025. Most production agents do not yet enforce against half of it.

96% of enterprises run AI agents in production. Only 12% have a central platform to manage them. Audit logs, agent identity, scope-limited credentials, and "hard no" execution boundaries are still mostly absent. The category that boards will mandate within 18 months is open.

A developer on Hacker News (December 2025) summarized it perfectly:

> *"A runtime layer for AI agents that enforces execution boundaries: traces, replay, and a hard 'no' when something unsafe is about to run."*

## Target user

- **Primary buyer:** CISO or VP Security at companies with regulated workloads.
- **Primary user:** Platform engineers who own the agent runtime.
- **Secondary:** Compliance teams preparing for SOC 2, ISO 27001, or EU AI Act audits.

## Value proposition

*"Agents you can put in production with the same confidence as the rest of your stack — auditable, scope-limited, and unable to do what they're not allowed to do."*

Demo line: **"This agent can read customer support tickets. It cannot send emails to customers. It cannot access billing data. Every action is logged. Every refusal has a reason. Sleep at night."**

## Key features (MVP)

1. **Policy-as-code DSL** — define agent boundaries declaratively. Example: `deny: tool=stripe.charge unless approval.human=true`.
2. **Runtime enforcement** — sits between the agent and its tools. Every tool call is policy-evaluated before execution; denials are surfaced to the agent (and logged) so it can adapt.
3. **Per-agent identity and scoped credentials** — every agent gets its own short-lived credential set. No shared API keys.
4. **Replay + time-travel debugging** — when an incident happens, replay the agent's reasoning, the policy evaluations, and the resulting tool decisions step-by-step. Built on Agent Trace SDK spans.
5. **OWASP Top-10 detector pack** — out-of-the-box rules covering each category in the OWASP Top 10 for Agentic Applications.
6. **Compliance evidence export** — SOC 2 / ISO 27001 / EU AI Act-flavored evidence reports. Audit log queryable, exportable, signed for tamper-evidence.
7. **Approval workflows** — when an action requires human approval (per policy), routes the request via Slack/Teams/email; agent waits for the response.

## Design direction

- **Conservative defaults.** Block first, allow with explicit policy. Easier to loosen than tighten.
- **Compliance language is the language.** Each policy should produce evidence in compliance-team words ("SOC 2 CC6.1 control evidence") not engineering words.
- **Replay is the killer demo.** Showing a CISO "watch the agent try to do X, watch us deny it, here's the audit trail" is the close.
- **Cool, formal palette.** This is sold to CISOs, not developers. Trust signals everywhere.

## Monetization

- **Standard:** $99/agent/mo for 1–10 agents.
- **Team:** $499/mo for unlimited agents in one workspace.
- **Enterprise:** $30K+/yr for SAML, audit log retention, on-prem deployment.
- **SOC 2 Compliance Bundle:** $80K+/yr — adds dedicated audit-readiness consulting, evidence export tailored per framework, third-party audit liaison support.

ROI math: a single avoided agent-related security incident (typical breach cost $4M+) pays for the entire DevTrust contract for years. Plus measurable acceleration of the audit cycle.

## Dependencies

- **Agent Trace SDK** at v1.5+ — AgentGuard's audit log is a structured view over trace spans plus its policy evaluation results.
- **Shared platform** auth, billing, dashboard.
- **External:** SAML provider, Slack/Teams for approvals, evidence storage backends (S3, GCS, Azure Blob).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Big platform vendors (Microsoft, Google, AWS) ship native agent governance | Compete on framework neutrality (we work with any agent stack) and depth of policy DSL. |
| Customers find policies too restrictive in practice | Ship a "shadow mode" where policies log denials but don't block, for the first 30 days of each new policy. Tune from real data. |
| Compliance certification of our own platform is expensive | Use Vanta / Drata for SOC 2 Type II in Year 1; ISO 27001 in Year 2. Build the customer's certification on top of ours. |
| LLM providers ship native guardrails that overlap | Position above provider guardrails: ours are policy-driven and cross-provider; theirs are model-specific. |

## Future roadmap

- v1.1: visual policy builder for non-engineers (compliance teams).
- v1.2: red-team integration — built-in adversarial prompts to test policy coverage before promoting to production.
- v1.3: cross-agent policy — when multiple agents collaborate, enforce policy at the orchestration layer.
- v2.0: continuous compliance — auto-detect drift between policies and observed behavior; alert when an agent starts acting "differently" even within allowed bounds.

## Validation plan (60-day kill criteria — slower because enterprise sale)

- 5 design partner companies committed before Wave 4 begins.
- 3 paid contracts signed by end of month 12.
- 1 SOC 2 Compliance Bundle sale by end of month 14.
- If 0 design partners commit during Wave 3 (when we start outreach), the positioning is wrong and we should reposition or kill before Wave 4 build starts.

## Why this in Wave 4

Enterprise security products require credibility. By Wave 4, DevTrust has shipped 4 OSS products (signaling community trust), 3 paid SaaS products (signaling commercial discipline), and the Agent Trace SDK has had 6 months to gain adoption in the wild. That stack is what AgentGuard's enterprise sales motion stands on. Earlier, this product is too early.
