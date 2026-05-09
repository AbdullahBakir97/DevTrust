# Smart Test Selector — changelog

All notable changes to `sts` are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.0.3] — 2026-05-08

### Added
- **Transitive-import affecting (sixth heuristic).** When a Repo X-ray v0.3+ artifact is loaded, sts builds the reverse-import graph from `call_graph.imports` and walks it outward from every changed source file (BFS, max depth 20). Any test that *transitively* imports a changed module becomes must-run, with reason `transitive import (depth N) of changed file`. Catches the case where a module deep in the codebase is the actual cause of a failure but isn't a sibling, mirror, or convention match.
- `RepoxArtifact.imports_by_source: dict[str, list[str]]` — new field carrying the file -> in-repo-targets map.
- `repox_integration.load_files` now extracts `call_graph.imports` from the artifact and populates `imports_by_source` (filtering out external deps with `target_file = None`).
- 4 new tests: two-hop transitive affecting, no-call-graph fallback (preserves old v0.0.2 behavior), `imports_by_source` extraction from artifact, schema-version assertion.

### Changed
- Schema bumped 0.1.0 → **0.2.0** (non-breaking — new dict field defaults to `{}`).

### Notes
- The transitive heuristic is **off by default unless** a repox v0.3+ artifact is present. Older artifacts (v0.0.x – v0.1.x) keep behaving exactly like sts v0.0.2.
- BFS depth cap of 20 is a safety net; normal monorepos see depth 1–4.

[0.0.3]: https://github.com/AbdullahBakir97/sts/compare/v0.0.2...v0.0.3

---

## [0.0.2] — 2026-05-07

### Added
- **Repo X-ray integration.** `sts` now reads `.repox/architecture.json` automatically when present, using its (gitignore-respecting) file list instead of doing its own walk. Faster and more accurate. Disable with `--no-use-repox`. (`src/sts/repox_integration.py`)
- **Package-boundary heuristic.** Tests inside the same package as a changed source file are now marked must-run. "Package" is defined by the nearest enclosing `pyproject.toml` / `package.json` / `Cargo.toml` / `go.mod`. This fixes the monorepo case where a file at `src/products/01-repo-xray/code/src/repox/analyzer.py` should pull tests at `src/products/01-repo-xray/code/tests/`.
- **`SelectionInputs.used_repox_artifact`** field — captures whether the selection used the repox artifact, for reproducibility.
- **`RepoxArtifact`** Pydantic model — captures the repox artifact's metadata in the selection report.
- New tests: artifact loading, malformed-artifact handling, package-boundary scoping (two-package monorepo), deep-nesting case, `--no-use-repox` flag.

### Changed
- Schema version bumped from **0.0.1 → 0.1.0** (non-breaking — old fields are unchanged; new field is optional).

[0.0.2]: https://github.com/AbdullahBakir97/sts/compare/v0.0.1...v0.0.2

---

## [0.0.1] — 2026-05-07

### Added
- Initial scaffold: `sts` Python package with three CLI commands (`select`, `version`, `info`).
- Pydantic v2 schema (versioned 0.0.1): `TestRef`, `TestSelection`, `SelectionReport`.
- `frameworks` module: detects pytest / jest / vitest / mocha / gotest / cargo by file path patterns.
- `selector` module: the affecting engine (manifest-edge, sibling tests, naming convention).
- `diff` module: parses changed-file lists from CLI args, plain file lists, or unified diff.
- `output` module: JSON and Markdown writers emitting to `.sts/selection.{json,md}`.
- Workspace-level dependency on `repox` — `sts` consumes the Repo X-ray architecture model.
- Smoke tests covering framework detection, manifest-edge selection, sibling-test affecting, CLI commands.
- Apache-2.0 license, hatchling build, typer/rich/pydantic/pathspec deps.

[0.0.1]: https://github.com/AbdullahBakir97/sts/releases/tag/v0.0.1
