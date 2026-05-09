# whychanged - changelog

All notable changes to `whychanged` are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-08

### Added
- **`GitHubDeploymentsProvider`** (`src/whychanged/providers_github.py`). Reads `GET /repos/{owner}/{repo}/deployments` via httpx, maps each deployment to a `Change` with `kind="deploy"`, `source="github-deployments"`, `actor=creator.login`, and a summary built from environment + ref + description. Pagination stops once it crosses `since` (the API returns deployments newest-first). Errors (HTTP 4xx/5xx, network) are logged and reduced to `[]` -- never propagate.
- **CLI flags** on `whychanged explain`: `--github-repo owner/name` to enable the provider, `--github-environment ENV` to filter (e.g. only `production` deploys).
- **Auth** via env vars: `WHYCHANGED_GITHUB_TOKEN` (preferred) or `GITHUB_TOKEN` (CI-runtime convention).
- 8 new tests with `httpx.MockTransport`: deployment-to-Change mapping, time-window filtering with newest-first pagination short-circuit, 5xx error tolerance, network-failure tolerance, env-var token resolution (both vars), CLI rejection of malformed `--github-repo`, structural version assertion.

### Changed
- Promoted from `Development Status :: 3 - Alpha` to `Development Status :: 4 - Beta`.
- `httpx>=0.27.0` added as a required dependency (was: no HTTP client).
- Schema unchanged. Version bump 0.0.1 -> 0.1.0.

### Notes
- The local `GitChangeProvider` (commits-as-deploys) remains the LCD fallback. Most teams will run BOTH providers in parallel: GitHub Deployments for the production-deploy story, git log for the "what landed on main since yesterday" story. The engine merges + ranks the combined stream.
- GitHub App installation tokens (JWT-based, no PATs) land in v0.2 alongside webhook mode (push WhyChanged reports as Slack alerts when an incident is detected).

[0.1.0]: https://github.com/AbdullahBakir97/whychanged/compare/v0.0.1...v0.1.0

---

## [0.0.1] - 2026-05-08

### Added
- Initial scaffold: `whychanged` Python package with two CLI commands (`explain`, `version`).
- Pydantic v2 schema (versioned 0.0.1): `Change`, `RankedChange`, `ChangeWindow`, `IncidentReport`. Six change kinds (`deploy`, `feature-flag`, `config`, `dependency`, `schema`, `unknown`).
- `providers` module:
  - `ChangeProvider` Protocol that any backend implements.
  - `GitChangeProvider` reads `git log` in a time window and turns commits into `kind="deploy"` Changes. Robust to missing `.git`, missing `git` binary, malformed log output.
- `engine` module: `explain()` orchestrates the providers, scores changes by recency (30-min half-life decay) + file-scope bonus + kind weight, returns a sorted `IncidentReport`.
- `output` module: JSON + Markdown writers emitting to `.whychanged/report.{json,md}`. The Markdown report leads with the top-ranked culprit + reason list.
- CLI flags: `--repo`, `--since`, `--incident-at`, `--service`, `--service-file` (repeatable), `--branch`, `--quiet`. `--since` accepts `30m`, `2h`, `3d` shorthand.
- 22 smoke tests covering: window-string parsing, recency decay (including post-incident exclusion), file bonus, service-file ranking boost, provider-exception shielding, git-log parsing edge cases, CLI artifact emission, schema-version assertion.
- Apache-2.0 license, hatchling build, typer/rich/pydantic deps.

### Notes
- Wave 3 lead-bet of the DevTrust platform.
- The 30-minute recency half-life and the kind-weight table are deterministic v0.0.1 defaults. v0.2 will replace the heuristic with an outcome-trained model once there's labeled data.

[0.0.1]: https://github.com/AbdullahBakir97/whychanged/releases/tag/v0.0.1
