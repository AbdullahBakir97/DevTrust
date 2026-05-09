# Smart Test Selector (`sts`)

> Given a PR diff, decide which tests must run, which should run, and which can safely skip.

`sts` is the Wave 1 revenue product of the DevTrust connected platform. It consumes the
codebase architecture model produced by [Repo X-ray](../../01-repo-xray/code) and applies
deterministic, repo-aware heuristics to select an effective subset of the test suite.

## Why

CI pipelines run the entire test suite on every PR because nobody trusts "affected tests"
detection. Builds take 30+ minutes. Developers ship less. The ROI is direct: minutes saved
per PR × PRs per week × engineer cost. A measurable, real-money problem.

## What v0.0.1 does

- Reads a list of changed files (from CLI args, a file, or unified diff).
- Identifies test files using framework patterns (pytest, jest/vitest, gotest, cargo).
- Classifies each test as **must-run**, **should-run**, or **can-skip** with a reason.
- Emits a JSON report (machine-consumable) and a terminal table (human-readable).

## Heuristics in v0.0.1

1. **Manifest changed** (pyproject.toml, package.json, Cargo.toml, go.mod, lockfiles)
   → run all tests. Dependency drift can break anything.
2. **A test file was directly modified** → run that test.
3. **A non-test source file was modified** → run sibling tests:
   - Tests in the same directory.
   - Tests matching naming conventions (`test_<name>.py`, `<name>.test.ts`, `<name>_test.go`).
   - Tests in the corresponding `tests/` subtree mirroring `src/`.
4. **No affected tests detected for a changed file** → mark all tests `should-run`
   (safe default; never silently skip on uncertainty).

Call-graph-aware affecting (which test transitively imports the changed module) lands
in v0.1 once Repo X-ray v0.2 ships its call graph.

## CLI

```bash
sts version
sts select --repo .                      # auto-detect changed files via git
sts select --repo . --changed src/foo.py src/bar.py
sts select --repo . --diff changes.diff
sts info --repo .                        # quick stats: how many tests, by framework
```

Output: a JSON report at `.sts/selection.json` and a terminal table.

## Status

v0.0.1: alpha. Apache-2.0. See [CHANGELOG](CHANGELOG.md).
