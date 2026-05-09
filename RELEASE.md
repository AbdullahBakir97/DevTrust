# Release process

This monorepo ships **eight independent packages** to PyPI, all under the
`devtrust-` namespace prefix:

| Distribution | Source path | What it does |
|---|---|---|
| `devtrust-repox`      | `src/products/01-repo-xray/code/` | Codebase architecture model (CLI + library) |
| `devtrust-sts`        | `src/products/02-smart-test-selector/code/` | Test selection engine (CLI + library) |
| `devtrust-sts-app`    | `src/products/02-smart-test-selector/app/` | GitHub App for sts |
| `devtrust-apr`        | `src/products/03-agent-pr-reviewer/code/` | PR review engine (CLI + library) |
| `devtrust-apr-app`    | `src/products/03-agent-pr-reviewer/app/` | GitHub App for apr |
| `devtrust-agtrace`    | `src/products/06-agent-trace-sdk/code/` | Agent-aware tracing (Wave 3) |
| `devtrust-whychanged` | `src/products/07-whychanged/code/` | Production diff-detective (Wave 3) |
| `devtrust-tokencost`  | `src/products/08-tokencost/code/` | LLM cost attribution (Wave 3) |

Each package versions independently. The release workflow fires on git tags
matching `<distribution>-v<version>` (e.g. `devtrust-repox-v0.4.0`) and
publishes that one package only.

## One-time setup (per package)

1. **Register a Trusted Publisher on PyPI** ("pending" mode is fine — the
   project is auto-created on first publish). For each project, go to
   `https://pypi.org/manage/account/publishing/` and add:
   - **PyPI Project Name:** `devtrust-<short>` (e.g. `devtrust-repox`)
   - **Owner:** `AbdullahBakir97`
   - **Repository name:** `DevTrust`
   - **Workflow name:** `release.yml`
   - **Environment name:** `pypi-devtrust-<short>` (e.g. `pypi-devtrust-repox`)
2. **Create the matching GitHub Environment.** Repo settings -> Environments
   -> `pypi-devtrust-<short>`. Add review gates if you want a human in the
   loop on first releases.

## Cutting a release

The whole flow takes about 90 seconds plus the workflow run.

```bash
# 1. Bump the package's version (edit BOTH locations)
#    -> src/products/<NN>-<name>/<sub>/pyproject.toml :: [project].version
#    -> src/products/<NN>-<name>/<sub>/src/<pkg>/__init__.py :: __version__

# 2. Add the release entry to the package's CHANGELOG.md
#    Header MUST be exactly `## [X.Y.Z] — YYYY-MM-DD` so release.py finds it.

# 3. Run the pre-flight gates locally
uv run python scripts/release.py --check --package devtrust-repox

# 4. Find the right tag string
uv run python scripts/release.py --tag-suggestion devtrust-repox
# -> devtrust-repox-v0.4.1

# 5. Commit, tag, push
git add .
git commit -m "Release devtrust-repox v0.4.1"
git tag devtrust-repox-v0.4.1
git push && git push --tags
```

The `release.yml` workflow takes over from there:

- Re-runs the pre-flight checks
- Builds wheel + sdist with `uv build --package <name>`
- Publishes via PyPI Trusted Publishing (no API tokens, OIDC-based)

## What the pre-flight script verifies

`scripts/release.py --check` is the gate. It:

1. Walks every workspace member under `src/products/*/{code,app}/`.
2. Confirms `pyproject.toml :: version` matches `__init__.py :: __version__`.
3. Confirms the package's `CHANGELOG.md` has a `## [<version>]` heading
   matching the version it's about to release.
4. Runs `ruff check`, `ruff format --check`, `mypy --strict`.
5. Runs `pytest --no-cov` for the package.

If any of those fail it exits 1 and the workflow aborts before touching PyPI.

## Recovery from a broken release

PyPI is append-only. You **cannot** re-upload the same version. If you
publish a broken release:

1. **Yank** it from PyPI (via the project page) so `pip install <pkg>` skips it.
2. Bump the patch version, fix the bug, and ship the next release normally.

## Manual one-off (without a tag)

Use the `workflow_dispatch` button on the Actions tab and supply the tag
string in the input. Same permissions and gates apply.
