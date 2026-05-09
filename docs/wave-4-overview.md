# Wave 4 — the runtime governance layer

> One opinionated tool that answers the question every CISO asks before signing
> off on a production AI agent:
> **what can this agent NOT do, and how do we prove it?**

DevTrust's Wave 4 isn't an AI safety platform. The AI safety market is full of model-level guardrails (jailbreak detectors, content filters) that protect against the model misbehaving. What's missing is a **runtime layer** that protects against the model **being right but the action being wrong** — every tool call, every decision, every outcome auditable, with a hard "no" when something unsafe is about to run.

## The one question, mapped

| Question | Tool | Headline output |
|---|---|---|
| **What can this agent NOT do, and how do we prove it?** | `agentguard` | A pure `evaluate(policy, call)` decision per tool invocation, an append-only JSONL audit log of every decision (allow / deny / require_approval), and conservative-by-default policies you can compose. |

It stands alone. The interesting story is what happens when you wire it through the rest of the DevTrust stack.

## The integration

`agentguard` and `agtrace` are designed to interlock. When a `with_agent("...")` block is open AND an `agtrace` span is active, every `evaluate()` call attaches its decision to the active span — so the trace tree shows BOTH the agent's reasoning AND the policy enforcement that gated each step.

```
agent.run (agent) (12ms)
├── agent=support-bot:installation-12345
└── tool.zendesk.read (tool_call) (4ms)
    ├── decision.status=allow
    ├── decision.matched_rule=allow-read-tickets
    └── decision.reason=Read-only access to support tickets.
└── tool.mail.send (tool_call) (1ms)
    ├── decision.status=deny
    ├── decision.matched_rule=deny-mail-send-with-secret
    ├── decision.reason=Outbound mail flagged as containing a secret...
    └── decision.tags=[owasp:llm02, secrets, mail]
```

**One trace = the agent's work AND its compliance trail.**

## The canonical setup (~10 lines of code)

```python
from agentguard import Policy, Rule, ToolCall, enforce, with_agent
from agentguard.baseline import baseline_starter_policy

policy = Policy(
    name="support-bot",
    rules=[
        # Your allow rules go FIRST — they short-circuit before the deny rules.
        Rule(name="allow-read-tickets", effect="allow",
             tool="zendesk.read",
             reason="Read-only access to support tickets."),
        # Then compose the conservative defaults from the baseline:
        *baseline_starter_policy().rules,
    ],
)

with with_agent("support-bot:installation-12345"):
    decision = enforce(
        policy,
        ToolCall(tool="zendesk.read", arguments={"ticket_id": 42}),
        audit="audit.jsonl",
    )
    if decision.status != "allow":
        raise PermissionError(decision.reason)
    # ... call zendesk.read for real
```

Three lines of imports, one composed policy, one `enforce()` per tool call. Everything else is application code.

## Why `agentguard` is sized this way

### Conservative-by-default is the design choice, not a feature

Anything not explicitly allowed is denied. Easier to loosen than tighten — and the asymmetry matters when the failure mode is "agent did something it shouldn't have." There's no `default_allow=True` flag in v0.0.1; if you want broad permission, write a broad allow rule and own it.

### First-rule-wins ordering is a design choice, too

Most policy engines try to be smart about rule precedence (specificity matching, weighted scoring). `agentguard` does the simplest thing: rules in order, first match decides. The cost is that you have to think about ordering; the benefit is that policy evaluation is trivially auditable. A compliance team can read top to bottom and reproduce the engine's decision in their head.

### The audit log is the API

`enforce(policy, call, audit=path)` writes one JSON line per decision. That file IS the compliance evidence. v0.1 ships replay tooling that re-runs the audit log to prove decisions were deterministic. v0.2 wires the file format into SOC 2 / ISO 27001 / EU AI Act evidence templates.

There is no separate database. There is no proprietary format. JSONL plays with every log shipper, every SIEM, every compliance tool already in the customer's stack.

### `require_approval` is honored but not yet round-tripped

v0.0.1's `evaluate()` returns Decision objects with status `"require_approval"` — your runtime can act on this however you want (Slack message, email, agent waits for input). The native round-trip integration ships in v0.2.

## What this is NOT

- **Not a model-level safety system.** It doesn't detect jailbreaks, prompt injection at the LLM layer, or harmful generation. Those are the model provider's problem; `agentguard` lives one layer up — at the **action** layer.
- **Not a sandbox.** It doesn't execute tools in a restricted environment or limit syscalls. It decides whether a call should run; running it is your runtime's job.
- **Not a DSL.** v0.0.1 policies are Python objects (`Policy`, `Rule`). v0.1 will ship a YAML format for ops teams who don't want to write Python.

## Status — May 2026

| Package | Version | Status |
|---|---|---|
| `devtrust-agentguard` | v0.0.1 | alpha — Python policy objects, deterministic engine, JSONL audit, three OWASP-flavored baselines, CLI |

Pass `mypy --strict` + `ruff check` + `ruff format --check`. 29 smoke tests cover models, engine, identity, baselines, CLI. Apache-2.0.

## Roadmap

- **v0.1** — YAML / TOML policy format. Full OWASP Top-10 detector pack. Replay-from-audit-log helper that re-runs decisions deterministically and proves they're stable.
- **v0.2** — Approval workflows: native Slack / Teams / email round-trips with timeout + retry. Shadow-mode (log denials but don't enforce) for the first 30 days of each new policy in production.
- **v0.3** — Replay + time-travel debugging via `agtrace` integration. Per-agent identity and scoped credentials.
- **v1.0** — Visual policy builder (compliance-team-friendly). Red-team integration (built-in adversarial prompts to test policy coverage). Cross-agent policies. Continuous compliance: auto-detect drift between policies and observed behavior.

## Where this fits in the broader DevTrust thesis

Wave 1 (`repox` + `sts` + `apr`) was the **trust layer for AI-augmented development** — codebase model, test selection, PR review.

Wave 2 (`sts-app` + `apr-app`) was the **ship layer** — bringing those engines to every PR, automatically.

Wave 3 (`agtrace` + `whychanged` + `tokencost`) was the **observability layer** — what the agent did, what changed, what it cost.

Wave 4 (`agentguard`) is the **governance layer** — what the agent IS and ISN'T allowed to do, with the audit trail to prove it.

Together they form **the trust stack for AI-era engineering — from PR to production.**

## Try it

```bash
pip install devtrust-agentguard

# Inspect the bundled baselines:
agentguard policies

# Dry-run a tool call against a policy:
agentguard check --tool stripe.charge --policy baseline-starter
agentguard check --tool fs.delete --policy destructive-filesystem \
                 --arguments-json '{"recursive":true}'
```

That's the whole story.
