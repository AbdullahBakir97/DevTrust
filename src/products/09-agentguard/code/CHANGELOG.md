# AgentGuard — changelog

All notable changes to `devtrust-agentguard` are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.0.1] — 2026-05-09

### Added
- **Initial scaffold.** Wave 4 product of the DevTrust platform — runtime governance layer that sits between an AI agent and its tools and decides, on every tool call, whether the call is permitted by the active policy.
- **Pydantic models** (`agentguard.models`):
  - `Policy` — ordered list of `Rule`s with a stable `schema_version` field.
  - `Rule` — `effect ∈ {allow, deny, require_approval}`, `tool` fnmatch glob, optional `when` argument-predicate dict, compliance-team-readable `reason`, free-form `tags`.
  - `ToolCall` — what an agent attempts; `tool`, `arguments`, optional `agent`.
  - `Decision` — what `evaluate()` returns; persisted to the audit JSONL exactly as-is.
- **Engine** (`agentguard.engine`):
  - `evaluate(policy, call)` — pure function, no side effects, deterministic. First-matching-rule-wins. No match → conservative default-deny.
  - `enforce(policy, call, audit=path)` — same plus appends the Decision as one line to a JSONL audit log; auto-creates the parent directory.
- **Identity** (`agentguard.identity`):
  - `with_agent("agent-id")` context manager + `current_agent()` getter.
  - ContextVar-backed so it's safe across threads and asyncio. Same pattern as `agtrace` / `tokencost`.
- **Baseline policies** (`agentguard.baseline`):
  - `deny_money_movement()` — Stripe / bank / PayPal namespaces.
  - `deny_destructive_filesystem()` — recursive deletes, `fs.rmtree`, `db.drop_*`.
  - `deny_credential_disclosure()` — outbound mail / HTTP POST flagged with predicate.
  - `baseline_starter_policy()` — composed view of all three for "drop-in starter."
- **CLI**: `agentguard version`, `agentguard policies` (list bundled baselines), `agentguard check --tool ... --policy ... --arguments-json ...` (dry-run).
- **34 smoke tests** covering: schema version pin, model validation, evaluate (default-deny, first-match, when-dict subset, fnmatch globs, agent inheritance from ContextVar, explicit-override), enforce (audit JSONL append, parent-dir creation, no-audit no-op), identity (ContextVar stack including nesting), baseline policies (Stripe / bank / recursive delete / composed starter), CLI (version, policies, check, unknown-policy error, invalid JSON, recursive route).

### Notes
- v0.0.1 is **deterministic-only by design.** Approval round-trips, OWASP Top-10 detector pack expansion, YAML policy DSL, and `agtrace` replay land in v0.1+.
- Conservative-by-default: any tool call that doesn't match any rule is denied. Easier to loosen than tighten.
- The `require_approval` effect is honored by `evaluate` (returns Decision with that status) but the round-trip to a human is left to the caller in v0.0.1. v0.2 ships native Slack / Teams / email integrations.
- Apache-2.0. Part of the DevTrust monorepo.

[0.0.1]: https://github.com/AbdullahBakir97/DevTrust/releases/tag/devtrust-agentguard-v0.0.1
