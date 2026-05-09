# 01 — Repo X-ray

> Codebase architecture model that AI tools and other DevTrust products consume.

| | |
|---|---|
| **Lane** | Open source · foundation |
| **Wave** | 1 (months 0–3) |
| **Lead user** | Individual developers; AI tools |
| **License** | Apache-2.0 |
| **Powers** | Smart Test Selector · Agent-PR Reviewer · Dep Upgrade Pilot · CI Local |

---

## Pain point

Every AI coding tool — Cursor, Claude Code, Copilot, Aider, Devin — re-derives a fresh, shallow understanding of your codebase on every session. There's no shared, persistent representation of "how this project actually works." The result: suggestions that ignore conventions, refactors that duplicate logic, and the universal complaint *"no AI actually understands my repo as a system."*

Repo X-ray fixes this with a single, open, structured artifact that any tool can read.

## Target user

- **Primary:** Developers maintaining medium-to-large repos (10K–500K LOC) who use AI tools daily.
- **Secondary:** Teams adopting AI-assisted development at the org level — they want consistent AI behavior across IDEs.
- **Tertiary:** Other DevTrust products (Smart Test Selector, Agent-PR Reviewer, Dep Upgrade Pilot all consume Repo X-ray output).

## Value proposition

*"One artifact. Every AI tool understands your repo the same way."*

Run `repox build` once and get a structured architecture brief — entry points, module boundaries, data flow, conventions, key abstractions, dependency graph. Drop the artifact in your repo, regenerate on PRs, and any AI tool that reads it gets immediate context.

## Key features (MVP, by end of Wave 1)

1. **`repox build`** — analyzes a repo and emits `.repox/architecture.json` plus a human-readable `.repox/architecture.md`.
2. **Static analysis modules** — call graph (via tree-sitter), entry-point detection, module-boundary inference, dependency graph from manifests, file-classification heuristics.
3. **Convention extraction** — naming patterns, common file structures, error handling style. Surfaces as a "conventions.md" companion file.
4. **Incremental updates** — `repox update` reruns only what changed since last build.
5. **MCP server** — exposes the architecture model as an MCP tool so Claude Code, Cursor, and any MCP-aware client read it directly.
6. **CI integration** — GitHub Action that regenerates on PR and posts a diff comment when architecture changes.

## Design direction

- **CLI first.** A developer should be able to install with `npm i -g repox` (or `pip install repox`, both equivalent) and produce useful output in under 30 seconds.
- **Output format is the product.** The schema is the API. Versioned, documented, stable.
- **Language-agnostic core, language-specific plugins.** Start with TypeScript / JavaScript, Python, Go, Rust as v0.1.
- **Beautiful default markdown.** When opened in GitHub or VS Code, the human-readable companion file should feel like a README a senior engineer wrote.

## Monetization

OSS core is free forever. Revenue comes from:

- **Hosted "always fresh" service** ($9/dev/mo, $19/team/mo) — auto-rebuilds architecture model on every push, hosts the latest version, syncs to all team members' AI tools without manual `repox update`.
- **Enterprise tier** ($25K+/yr) — multi-repo views, monorepo support, security hardening, SSO, audit logs.

## Dependencies

- **Foundation:** none — Repo X-ray is itself a foundation.
- **Infrastructure (hosted variant only):** Auth, Billing, UI shell from `00-shared-platform`.
- **External:** tree-sitter, LSP servers, language-specific parsers.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Big AI tools (Cursor, Claude) ship native repo understanding and Repo X-ray is commoditized | Make the artifact format the standard. Even if Cursor builds its own, an open format that all tools agree on still wins. |
| Generated artifacts are noisy or wrong | Aggressive testing on a curated set of 50+ real-world OSS repos before v1.0. Quality bar: a senior eng reading the output should not say "this is wrong." |
| MCP adoption stalls | Ship adapters for direct file-read by major IDEs as backup distribution. |

## Future roadmap (post-Wave 1)

- v1.1: language coverage extends to Java, C#, Ruby, PHP, Kotlin.
- v1.2: custom convention rules — teams can extend the conventions extractor with their own DSL.
- v1.3: temporal view — "how has this repo's architecture changed over the last 6 months?"
- v2.0: cross-repo views for monorepos and microservice constellations.

## Validation plan (30-day kill criteria)

- 200+ waitlist signups from organic posts on r/programming, HN, Mastodon — pass.
- 5+ paying design partners on the hosted tier — pass.
- 100+ GitHub stars in first month — pass.
- If any of these miss by more than 50%: iterate twice on positioning, then re-evaluate.

## Why this is the foundation, not a feature

If Repo X-ray exists, then Smart Test Selector becomes "select tests using Repo X-ray's call graph." Agent-PR Reviewer becomes "compare PR diff against Repo X-ray's conventions and dependency graph." Dep Upgrade Pilot becomes "upgrade dependencies safely using Repo X-ray's import graph." Three products' worth of analysis, written once.

## Built on (existing assets)

Three of Abdullah's existing repos give Repo X-ray a meaningful head start instead of a greenfield build:

- [`Repo-Directory-Structure`](https://github.com/AbdullahBakir97/Repo-Directory-Structure) — direct ancestor. Tree-style repo snapshot already implements the directory analysis pipeline. Extend with call-graph and convention extraction.
- [`GitHub-Doc-Generator`](https://github.com/AbdullahBakir97/GitHub-Doc-Generator) — README parsing and Markdown output. Reusable for the human-readable `architecture.md` companion file.
- [`repodoc-ai`](https://github.com/AbdullahBakir97/repodoc-ai) — different output (README text vs. structured architecture) but the repo-scanning pipeline is shared. Reuse the analyzer.

**Estimated time saved in Wave 1: 3–4 weeks.** Recovered time should be spent on Smart Test Selector de-risking or pulling Wave 2 forward by 2 weeks.
