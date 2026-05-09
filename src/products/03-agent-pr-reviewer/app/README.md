# Agent-PR Reviewer — GitHub App (`apr-app`)

> A FastAPI service that runs the `apr` engine on every pull request and posts the verdict as a sticky comment.

## Status

**v0.0.1 alpha.** Same overall shape as `sts-app`: HMAC-verified webhooks, GitHub App JWT auth, tempdir-based per-file review.

## What it does

1. Receives `pull_request` webhook deliveries from GitHub.
2. Verifies the HMAC signature with `APR_APP_WEBHOOK_SECRET`.
3. Calls the GitHub API to:
   - Fetch the PR's title + body + head SHA (`GET /pulls/{n}`)
   - List the PR's changed files (`GET /pulls/{n}/files`)
   - Download each known-extension changed file's contents (`GET /contents/{path}?ref=SHA`) into a temp directory
4. Runs `apr.engine.review()` against the temp directory with the PR title + description.
5. Formats the `ReviewReport` as Markdown and either creates a sticky comment on the PR or updates the existing one (identified by an HTML marker).
6. Cleans up the temp directory.

## Configuration

All settings are read from environment variables prefixed `APR_APP_`. A `.env` file in the working directory is also loaded automatically.

| Variable | Default | Required for production |
|---|---|---|
| `APR_APP_HOST` | `127.0.0.1` | no |
| `APR_APP_PORT` | `8000` | no |
| `APR_APP_LOG_LEVEL` | `info` | no |
| `APR_APP_RELOAD` | `false` | no |
| `APR_APP_WEBHOOK_SECRET` | _none_ | **yes** — without it, signature verification is skipped |
| `APR_APP_APP_ID` | _none_ | **yes for production** — numeric GitHub App ID |
| `APR_APP_PRIVATE_KEY_PEM` | _none_ | **yes for production** — App's RSA private key (paste PEM contents) |
| `APR_APP_GITHUB_TOKEN` | _none_ | only for dev — Personal Access Token (ignored when App ID + key are set) |
| `APR_APP_GITHUB_API_URL` | `https://api.github.com` | no — override for GHES |
| `APR_APP_MAX_CHANGED_FILES` | `100` | no — beyond this we run metadata-only |
| `APR_APP_MAX_FILE_BYTES` | `512000` | no — skip per-file rules on larger files |
| `APR_APP_REQUEST_TIMEOUT_SECONDS` | `20` | no |

## Running locally

```bash
uv sync --all-packages --all-groups
export APR_APP_WEBHOOK_SECRET="something-long-and-random"
export APR_APP_GITHUB_TOKEN="ghp_..."
apr-app
# or
python -m apr_app

# Smoke check
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/version
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Service identity (name, version) |
| `GET` | `/health` | Liveness probe |
| `GET` | `/version` | App + engine versions |
| `POST` | `/webhooks/github` | Webhook receiver — must have valid `X-Hub-Signature-256` |
| `GET` | `/docs` | OpenAPI spec |

## Sticky comment format

The bot's comment includes:
- A hidden HTML marker so subsequent runs find and update it
- An emoji headline summarizing the worst severity (🛑 critical / ❌ error / ⚠️ warning / ℹ️ info / ✅ clean)
- Counts by severity
- A table of up to 30 findings with severity, file:line, rule_id, and message
- Footer with `apr` engine version + schema version + changed-file count

## Apache-2.0 license. See [CHANGELOG](CHANGELOG.md).
