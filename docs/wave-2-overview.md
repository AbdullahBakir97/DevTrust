# Wave 2 — the ship layer

> Two GitHub Apps that bring Wave 1's engines to every pull request, automatically.
> **`sts-app` selects the tests · `apr-app` reviews the diff · both post sticky comments.**

DevTrust's Wave 2 isn't another GitHub App. The market is saturated with single-feature bots that each demand their own install, their own webhook, their own surface area in the PR. What's missing is a **disciplined, reusable shape** for "drop our engine on every PR" that's honest about its boundaries — and that means the engines (Wave 1) stay separable from the shipping surfaces.

## The two apps, mapped

| App | Engine it drives | Headline output |
|---|---|---|
| `sts-app` | [`sts`](../src/products/02-smart-test-selector/code/) | Sticky PR comment with the test verdict: which tests must run, which can skip, why. |
| `apr-app` | [`apr`](../src/products/03-agent-pr-reviewer/code/) | Sticky PR comment with deterministic + AI-pattern review findings. |

Each is a small FastAPI service with the same architectural shape: webhook → JWT auth → tarball clone → run engine → upsert sticky comment.

## The same shape twice

Both apps follow exactly the same pattern, by design:

```
GitHub.com                    Your VPS / Render / Fly / EKS
─────────────                 ─────────────────────────────
PR opened   ──webhook──>      sts-app or apr-app
                              │
                              ├── HMAC-verify the webhook
                              ├── Mint installation token (RS256 JWT)
                              ├── Stream tarball of the PR ref
                              ├── Run repox build .
                              ├── Run engine (sts select OR apr review)
                              ├── Render Markdown comment
                              └── Upsert sticky comment via PR Reviews API
                                  │
                                  └──< POST <— GitHub
```

When you've seen one, you've seen the other. That's intentional: future apps for any DevTrust engine slot in by copying this shape.

## Why this is two apps, not one

A single "DevTrust App" install would be _easier to onboard_ but harder to govern. Different teams want different things turned on:

- A team adopting sts (smart test selection) but not apr (AI PR review) shouldn't have to install both.
- A team that wants apr's deterministic rules but not its LLM-backed checks shouldn't have to disable feature flags inside one mega-app.
- A team that wants to self-host one and use the hosted version of the other should be able to.

Two narrow apps with the same shape gives you that flexibility. They share zero state and can be deployed independently.

## What's deliberately **not** in either app

These were tempting and we said no:

- **No agent.** No "ask the model what it thinks" step in the webhook critical path. Engines are deterministic by default; opt-in LLM checks (apr's `ai-review:diff-comprehension`) live behind a flag and a separate API key.
- **No DB.** Both apps are stateless. The PR is the state. The sticky-comment ID is recovered by querying GitHub. If the app dies mid-request, GitHub re-delivers the webhook and we redo the work.
- **No `git` binary.** Both apps clone via the GitHub tarball endpoint over HTTPS. One fewer system dependency, and tarball auth uses the same installation token we already mint.
- **No background queue.** v0.0.x runs the engine inline within the webhook request. Slow PRs (~minute-long) just hold the request. A queue ships when we have a customer pushing PRs faster than that.

## Security model

| Concern | How it's handled |
|---|---|
| Webhook authenticity | HMAC-SHA256 with `X-Hub-Signature-256`, `WEBHOOK_SECRET` env var. Constant-time compare. |
| GitHub API auth | Per-installation RS256 JWT signed with the GitHub App's private key (PEM). Tokens cached for ≤55 min, re-minted on demand. |
| Tarball safety | Streaming download with a size cap. Extraction rejects absolute paths, parent traversals, and symlinks (`extract_safely` in `clone.py`). |
| Comment auth | Same installation token. Sticky-comment upsert via PR Reviews API. |
| Code persistence | None. Tarball extracted to `tempfile`, deleted after run. |

Both apps follow this exact security model. If one passes a security review, the other does too.

## What the sticky comment looks like

`sts-app` (Smart Test Selector):

```
🧪 Smart Test Selector v0.0.3 · 47 tests collected
- must_run: 12 (3 manifest changes, 9 transitive imports)
- should_run: 8 (sibling-test, mirror-tree)
- safe_skip: 27

<details><summary>full verdict</summary>
... markdown table per test ...
</details>
```

`apr-app` (Agent-PR Reviewer):

```
🔎 Agent-PR Reviewer v0.2.0 · 4 findings
- ⚠️ src/api/users.py:42 — broad-except (warning, quality)
- 🚨 src/cli.py:7 — hardcoded-secret (critical, security)
- ℹ️ src/web/app.tsx:12 — console-log (info, quality)
- ⚠️ src/lib/util.py:99 — ai-review:hallucinated-symbol (warning, ai-pattern)

<details><summary>suggested fixes</summary>
... ranked top-10 with line links ...
</details>
```

Both comments are upserted, not appended. The reviewer sees one comment per app per PR, always reflecting the latest commit.

## Status — May 2026

| Package | Version | Status |
|---|---|---|
| `devtrust-sts-app` | v0.0.3 | alpha — JWT installation tokens, HMAC webhook auth, tarball clone, end-to-end repox→sts→PR comment |
| `devtrust-apr-app` | v0.0.1 | alpha — same shape as sts-app, drives apr engine |

Both pass `mypy --strict` + `ruff check` + `ruff format --check`. Apache-2.0. PyPI live.

## Self-host vs DevTrust Cloud

Both apps are open-source FastAPI services you can deploy to any VPS, Render, Fly, EKS, etc. — `pip install devtrust-sts-app && sts-app run` and you have a working GitHub App webhook receiver. You bring the GitHub App registration, the private key, and the webhook secret.

If you'd rather not register two GitHub Apps, manage two private keys, run two webhook receivers, and aggregate the resulting comments yourself — **DevTrust Cloud** is the hosted version. One install, one dashboard, one billing line. See [DevTrust Cloud — coming soon](../README.md#devtrust-cloud--coming-soon).

## Where this fits in the broader DevTrust thesis

Wave 1 was the **trust engines** (`repox`, `sts`, `apr`).

Wave 2 is the **ship layer** — bringing those engines to every pull request, automatically, at the lowest possible operational cost.

Wave 3 is the **observability layer** for production.

Wave 4 is the **governance layer** for runtime AI agents.

Together they form **the trust stack for AI-era engineering — from PR to production.**

## Try it

```bash
# Install both (after registering GitHub Apps in your org):
pip install devtrust-sts-app devtrust-apr-app

# Run sts-app locally:
export STS_GITHUB_APP_ID=...
export STS_GITHUB_APP_PRIVATE_KEY_PATH=/path/to/key.pem
export STS_WEBHOOK_SECRET=...
sts-app run --port 8080

# In another terminal, run apr-app on a different port:
export APR_GITHUB_APP_ID=...
export APR_GITHUB_APP_PRIVATE_KEY_PATH=/path/to/apr-key.pem
export APR_WEBHOOK_SECRET=...
apr-app run --port 8081
```

Point your GitHub Apps' webhook URLs at the two services (separate ngrok tunnels in dev; separate hostnames in prod). Open a PR. Watch both comments land within a minute.

That's the whole story.
