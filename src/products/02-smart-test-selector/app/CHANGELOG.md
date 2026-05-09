# sts-app — changelog

All notable changes to `sts-app` are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.0.3] — 2026-05-08

### Added
- **Tarball clone path** (`src/sts_app/clone.py`). The handler now:
  1. Lists changed files via the GitHub API.
  2. Downloads the repo at the PR head SHA via `GET /repos/{owner}/{repo}/tarball/{sha}` (no `git` binary required on the host).
  3. Extracts it to a temp directory with **zip-slip / tar-slip protection** (path-escape entries rejected) and **symlink skipping** (no link-follow attacks).
  4. Caps the streamed download at `max_repo_bytes` (default 200 MB) — `TarballTooLargeError` raised on overflow.
  5. Runs `repox.analyzer.analyze()` against the extracted root.
  6. Builds a `sts.models.RepoxArtifact` (with `imports_by_source` from the call graph) and calls `sts.selector.select()` with it. **Transitive-import affecting now lights up in production.**
- New orchestrator module `src/sts_app/review.py` with `fetch_clone_and_select()` + `select_with_full_review()`. Mockable via `_run_repox_analyze` for tests.
- New env vars: `STS_APP_ENABLE_FULL_REVIEW` (default `true`) and `STS_APP_MAX_REPO_BYTES` (default 200 MB).
- 5 new tests: tar-slip rejection, symlink skipping, PR-files row cleaner (skips removed + dedupes), tarball size cap, end-to-end `select_with_full_review` with a stub Architecture (transitive heuristic must fire).

### Changed
- Handler falls back to v0.0.2's Tree-API path on any clone/analyze failure — a transient hiccup never breaks review.
- The `ok` response now includes `full_review: bool` so operators can monitor adoption + fallback rate.
- Default `request_timeout_seconds` raised to 60 (was 20) to accommodate the tarball download.

### Notes
- Schema unchanged. Just version bump 0.0.2 → 0.0.3 on `sts-app`.
- Performance: large PRs in big repos may exceed the configured timeout. Operators tune `STS_APP_REQUEST_TIMEOUT_SECONDS` and `STS_APP_MAX_REPO_BYTES` per workload.

[0.0.3]: https://github.com/AbdullahBakir97/sts/compare/sts-app-v0.0.2...sts-app-v0.0.3

---

## [0.0.2] — 2026-05-08

### Added
- **GitHub App authentication.** New `auth.py` module signs a 9-minute JWT with the App's RSA private key (`RS256`), exchanges it for an installation token via `POST /app/installations/{id}/access_tokens`, and caches the token in memory until it expires (with a 60-second safety margin). Replaces the v0.0.1 PAT-only mode for production deploys.
- New env vars: `STS_APP_APP_ID` and `STS_APP_PRIVATE_KEY_PEM` (paste the PEM contents directly). When both are set, the App-auth path is used and `STS_APP_GITHUB_TOKEN` is ignored.
- `pyjwt[crypto]>=2.9.0` added as a required dependency (brings in `cryptography` for RSA signing).
- 5 new tests: JWT round-trip with the matching public key, installation-token cache behavior under repeated calls, `auth_from_settings` returning None vs. an instance, the handler's `skipped` response when no auth is configured.

### Changed
- The handler's auth resolution now prefers the App path. Falls back to PAT only when the App credentials are absent (dev mode). When neither is set, the handler returns a clear `{"status":"skipped","reason":"no auth configured: set STS_APP_APP_ID + STS_APP_PRIVATE_KEY_PEM (production) or STS_APP_GITHUB_TOKEN (dev)"}` instead of just complaining about the missing PAT.

### Notes
- Repo cloning + running `repox build` against the PR head SHA is deferred to v0.0.3. v0.0.2 still uses the GitHub Tree API for the file list, which means the call-graph-aware affecting from sts v0.0.3 doesn't yet light up in the App path. v0.0.3 closes that gap.

[0.0.2]: https://github.com/AbdullahBakir97/sts/compare/sts-app-v0.0.1...sts-app-v0.0.2

---

## [0.0.1] — 2026-05-07

### Added
- Initial scaffold: FastAPI service with `/`, `/health`, `/version`, and `/webhooks/github` routes.
- HMAC-SHA256 signature verification (`security` module) using `hmac.compare_digest` for constant-time comparison.
- Async GitHub REST client (`github` module) — covers list-PR-files, list-tree, find/create/update-comment endpoints. No GitHub SDK dependency.
- Pull-request event handler (`handlers` module) — fetches PR files + repo tree, runs `sts.selector.select()`, formats the report as Markdown, upserts a sticky PR comment.
- `pydantic-settings`-based config (`config` module) with env-var prefix `STS_APP_`.
- Workspace dep on `sts` (the engine).
- 17 smoke tests covering: signature verification (good/bad/missing/dev-mode), comment formatter, all four HTTP routes, webhook signature rejection, ignored events, opened-PR + synchronize flows with mocked GitHub API.
- Apache-2.0 license, hatchling build, FastAPI / uvicorn / httpx / pydantic / pydantic-settings deps.

### Notes
- Authentication uses a Personal Access Token (`STS_APP_GITHUB_TOKEN`). Real GitHub App installation tokens (JWT) come in v0.0.2.
- Without `STS_APP_WEBHOOK_SECRET`, signature verification is **skipped** with a logged warning. **Do not run that mode in production.**

[0.0.1]: https://github.com/AbdullahBakir97/sts/releases/tag/sts-app-v0.0.1
