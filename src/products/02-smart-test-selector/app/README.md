# Smart Test Selector — GitHub App (`sts-app`)

> A small FastAPI service that runs the `sts` engine on every pull request and posts the verdict as a sticky comment.

## Status

**v0.0.1 alpha.** Authentication uses a Personal Access Token. Real GitHub App installation tokens are coming in v0.0.2.

## What it does

1. Receives `pull_request` webhook deliveries from GitHub.
2. Verifies the HMAC signature using `STS_APP_WEBHOOK_SECRET`.
3. Calls the GitHub API to:
   - List the PR's changed files (`GET /repos/.../pulls/.../files`)
   - Get the full file tree at the PR head SHA (`GET /repos/.../git/trees/{sha}?recursive=1`)
4. Runs `sts.selector.select()` against those two file lists.
5. Formats the `SelectionReport` as Markdown and either creates a sticky comment on the PR or updates the existing one (identified by an HTML marker).

## Configuration

All settings are read from environment variables prefixed `STS_APP_`. A `.env` file in the working directory is also loaded automatically.

| Variable | Default | Required for production |
|---|---|---|
| `STS_APP_HOST` | `127.0.0.1` | no |
| `STS_APP_PORT` | `8000` | no |
| `STS_APP_LOG_LEVEL` | `info` | no |
| `STS_APP_RELOAD` | `false` | no — set true for dev |
| `STS_APP_WEBHOOK_SECRET` | _none_ | **yes** — without it, signature verification is skipped |
| `STS_APP_APP_ID` | _none_ | **yes for production** — numeric GitHub App ID |
| `STS_APP_PRIVATE_KEY_PEM` | _none_ | **yes for production** — App's RSA private key (paste PEM contents) |
| `STS_APP_GITHUB_TOKEN` | _none_ | only for dev — Personal Access Token (ignored when App ID + key are set) |
| `STS_APP_GITHUB_API_URL` | `https://api.github.com` | no — override for GHES |
| `STS_APP_MAX_CHANGED_FILES` | `2000` | no — safety cap |
| `STS_APP_REQUEST_TIMEOUT_SECONDS` | `20` | no |

## Running locally

```bash
# From the project root
uv sync --all-packages --all-groups

# Set the env vars
export STS_APP_WEBHOOK_SECRET="something-long-and-random"
export STS_APP_GITHUB_TOKEN="ghp_..."

# Start the service
sts-app
# or
python -m sts_app

# In another shell, point a webhook at it (use ngrok / smee.io for HTTPS).
# GitHub: Settings -> Webhooks -> Add webhook
#   Payload URL: https://<your-tunnel>/webhooks/github
#   Content type: application/json
#   Secret: <same value as STS_APP_WEBHOOK_SECRET>
#   Events: Pull requests
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Service identity (name, version) |
| `GET` | `/health` | Liveness probe |
| `GET` | `/version` | App + engine versions |
| `POST` | `/webhooks/github` | Webhook receiver — must have valid `X-Hub-Signature-256` |
| `GET` | `/docs` | OpenAPI spec |

## Security notes

- HMAC-SHA256 signature verification is **always on** when `STS_APP_WEBHOOK_SECRET` is set. Constant-time comparison via `hmac.compare_digest`.
- GitHub tokens are never logged. They live in a `pydantic.SecretStr` and are only de-referenced at the boundary of an outgoing HTTP request.
- The webhook handler **never raises** — errors are logged and returned as JSON with a non-2xx-only-on-bad-signature policy. Webhook delivery dashboards stay green.

## Apache-2.0 license. See [CHANGELOG](CHANGELOG.md).
