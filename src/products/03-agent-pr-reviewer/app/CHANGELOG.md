# apr-app — changelog

All notable changes to `apr-app` are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.0.1] — 2026-05-08

### Added
- Initial scaffold: FastAPI service with `/`, `/health`, `/version`, and `/webhooks/github` routes.
- HMAC-SHA256 signature verification (`security` module) using `hmac.compare_digest` for constant-time comparison.
- GitHub App JWT authentication (`auth` module) — RSA-signed JWT, installation token exchange, in-memory cache. Personal-Access-Token preserved as dev fallback.
- Async GitHub REST client (`github` module) covering: `GET /pulls/{n}`, `GET /pulls/{n}/files`, `GET /contents/{path}`, `find/create/update sticky comment`.
- Pull-request event handler (`handlers` module):
  - On `pull_request.{opened, synchronize, reopened, ready_for_review}`:
    - Fetches PR metadata (title, body, head SHA).
    - Lists changed files; for each known-extension file under `max_file_bytes`, downloads contents to a temp dir.
    - Runs `apr.engine.review()` against the temp dir with the PR title + description.
    - Posts (or updates) a sticky comment formatted with severity counts, an emoji ladder (🛑/❌/⚠️/ℹ️/✅), and up to 30 finding rows.
    - Cleans up the temp dir.
  - Fallback: PRs with more than `max_changed_files` (default 100) get a metadata-only review.
- `pydantic-settings`-based config with env-var prefix `APR_APP_`.
- Workspace dep on `apr` (the engine).
- 22 smoke tests covering: signature verification (good/bad/missing/dev), comment formatting + emoji ladder, all four HTTP routes, webhook signature rejection, ignored events / unhandled actions, opened-PR clean-flow, finding-flow with bare-except file, synchronize-update flow, all four handled actions parametrized, "no auth configured" fallback path.
- Apache-2.0 license, hatchling build, FastAPI / uvicorn / httpx / pydantic / pydantic-settings / pyjwt[crypto] deps.

### Notes
- Repo cloning is not used — apr-app downloads exactly the files it needs to grade via the Contents API. This avoids requiring `git` on the host and keeps cold-start fast.
- Because no clone happens, the AI rule `ai-review:hallucinated-symbol` (which reads `.repox/architecture.json`) is not yet enabled in the App path. v0.0.2 will add an opt-in mode that runs `repox build` against the temp dir before `apr review`.

[0.0.1]: https://github.com/AbdullahBakir97/apr/releases/tag/apr-app-v0.0.1
