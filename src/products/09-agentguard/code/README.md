# AgentGuard (`devtrust-agentguard`)

> Policy-as-code runtime for AI agents — audit log + hard-no enforcement.
> The Wave 4 governance layer of the DevTrust platform.

## Status

**v0.0.1 alpha** — deterministic policy engine, ContextVar-based agent identity, JSONL audit log, three bundled baseline policies (`money-movement`, `destructive-filesystem`, `credential-disclosure`) plus a composed `baseline-starter`. CLI for dry-runs.

What ships in v0.0.1:

- **Pydantic models** — `Policy`, `Rule`, `ToolCall`, `Decision`. The on-disk audit-log shape is the same as the in-memory shape; no transformation between them.
- **`evaluate(policy, call)`** — pure function. First-matching-rule-wins. No-match → conservative default-deny.
- **`enforce(policy, call, audit=...)`** — same evaluation, plus appends the Decision as one JSON line to an audit file.
- **`with_agent("...")` / `current_agent()`** — ContextVar that survives threads and asyncio. Same pattern as `agtrace` and `tokencost`.
- **Three baseline policies** — opinionated deterministic defaults covering the OWASP Top-10 categories most expressible without an expression DSL.
- **CLI** — `agentguard version`, `agentguard policies`, `agentguard check`.

## Why

OWASP published a Top-10 for Agentic Applications in December 2025. 96% of enterprises run AI agents in production; only 12% have a central platform to manage them. AgentGuard is the runtime layer that enforces "this agent can read tickets but cannot send mail," with an auditable trail of every allow / deny / approval-needed decision.

Conservative-by-default is the design choice: anything not explicitly allowed is denied. Easier to loosen than tighten.

## CLI

```bash
agentguard version
agentguard policies
agentguard check --tool stripe.charge --policy baseline-starter
agentguard check --tool fs.delete --policy destructive-filesystem \
                 --arguments-json '{"recursive":true}'
```

## Library use

```python
from agentguard import Policy, Rule, ToolCall, evaluate, enforce, with_agent
from agentguard.baseline import baseline_starter_policy

policy = Policy(
    name="my-agent",
    rules=[
        # Allow rules go FIRST — they short-circuit before the deny rules.
        Rule(name="allow-read-tickets", effect="allow",
             tool="zendesk.read", reason="Read-only access to support tickets."),
        # Then compose the conservative defaults:
        *baseline_starter_policy().rules,
    ],
)

with with_agent("support-bot:installation-12345"):
    decision = enforce(
        policy,
        ToolCall(tool="zendesk.read", arguments={"ticket_id": 42}),
        audit="audit.jsonl",
    )
    if decision.status == "allow":
        # ... call zendesk.read for real
        pass
    else:
        raise PermissionError(decision.reason)
```

## Roadmap

- **v0.1** — YAML / TOML policy file format; OWASP Top-10 detector pack (full); replay-from-audit-log helper that re-runs decisions deterministically.
- **v0.2** — approval workflows (Slack / Teams / email round-trips with timeout + retry); shadow-mode (log denials but don't enforce, for the first 30 days of each new policy).
- **v0.3** — replay + time-travel debugging via `agtrace` integration; per-agent identity and scoped credentials.
- **v1.0** — visual policy builder (compliance-team-friendly), red-team integration, cross-agent policies, continuous compliance.

## Apache-2.0

See [CHANGELOG](CHANGELOG.md). Part of the [DevTrust monorepo](https://github.com/AbdullahBakir97/DevTrust).
