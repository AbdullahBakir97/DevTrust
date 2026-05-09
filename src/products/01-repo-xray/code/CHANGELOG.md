# Repo X-ray — changelog

All notable changes to `repox` are documented here. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — 2026-05-08

### Added
- **JS / TS function-call edges.** `repox.callgraph_ts.extract_one` now returns a third element — a list of `CallEdge` rows — alongside imports and symbols. For each `call_expression` inside a function or class body, repox emits an edge with the callee resolved against:
  1. the file's local function / class declarations (same-file calls)
  2. the file's imported names (`import { f } from './x'` -> `f` resolves to the file `./x` resolves to)
  Member calls like `obj.method()` and `a.b.c()` are recorded with their full dotted name.
- 4 new tests: imported-function call resolves to target_file, same-file call, unresolved global call (`console.log`) with target_file=None, version-bump assertion.

### Changed
- `extract_all` in `callgraph_ts` now returns `tuple[list[Import], list[Symbol], list[CallEdge]]`. `callgraph.py` aggregates all three into the unified `CallGraph`.
- Schema unchanged (still 0.3.0 — additive: same `CallEdge` shape, just more rows).

### Notes
- JavaScript-specific limitations intentionally not addressed in v0.4: closures, hoisting (forward references that need a two-pass walk), and default-export name resolution (we resolve to the file but not to a specific symbol within it). v0.5 may add a two-pass walk.
- The unified call graph (Python `ast` edges + JS/TS tree-sitter edges) is what powers `apr`'s `ai-review:hallucinated-symbol` rule and `sts`'s transitive-import affecting heuristic. v0.4 lights both up for JS/TS codebases that until now only got imports + symbols.

[0.4.0]: https://github.com/AbdullahBakir97/repox/compare/v0.3.0...v0.4.0

---

## [0.3.0] — 2026-05-08

### Added
- **Function-call edges (Python).** New `CallEdge` Pydantic model on `CallGraph.edges`. Walks every `FunctionDef` body and emits one edge per `Call` node with the callee resolved to an in-repo file when possible. Resolution covers: `from x import f; f()`, same-file calls to top-level functions/classes, dotted attribute calls (`obj.method()`).
- **Tree-sitter JS / TS extraction.** New `repox.callgraph_ts` module. Extracts ES6 imports (`import { x } from 'mod'`, `import * as ns`, side-effect `import 'mod'`), CommonJS (`require()`), and top-level symbols (function declarations, class declarations, `const`/`let` bindings, exported variants).
- `CallGraph.callers_of(target_file)` helper — returns the list of source files that have at least one edge resolving to that target.
- 6 new tests covering call-edge extraction, same-file resolution, unresolved (built-in) calls, the `callers_of` helper, schema-version assertion, and JS/TS imports + symbols.

### Changed
- `tree-sitter>=0.23` and `tree-sitter-language-pack>=0.4` graduated from `[project.optional-dependencies]` to required `dependencies`.
- Schema bumped 0.2.0 → **0.3.0** (non-breaking — `edges` defaults to `[]` so old readers ignore it).

### Notes
- JS / TS function-call edges are deferred to v0.4. JavaScript's call resolution (closures, hoisting, default exports, dynamic dispatch) makes static call-graph extraction substantially harder than for Python; doing it badly would generate noisy must-run signals in downstream consumers like `sts`.
- Per-file failures (syntax errors, encoding issues, tree-sitter parse failures) never abort a build — bad files are skipped silently.

---

## [0.2.0] — 2026-05-07

### Added
- New `callgraph` module — Python `ast`-based extraction of imports + top-level symbols (functions, classes, methods, top-level variables). No tree-sitter dependency required for v0.2; `tree-sitter` ships in v0.3 alongside JS / TS / Go / Rust support.
- New Pydantic models in `repox.models`: `Import`, `Symbol`, `CallGraph`. Schema bumped to **0.2.0**.
- `Architecture.call_graph: CallGraph | None` — populated when the repo has Python source.
- Convenience methods on `CallGraph`: `imports_by_file()` and `files_importing(target)` for downstream consumers.
- Markdown writer renders a new **## Call graph** section with totals + a "Most imported (top 10)" table.

### Changed
- Schema version bumped 0.1.0 → 0.2.0 (non-breaking — `call_graph` is optional; old readers ignore it).
- `analyzer.py` runs `callgraph.extract` after the file walk and threads the result through to `Architecture`.

### Notes
- Python target resolution: `from a.b.c import x` resolves to `a/b/c.py` or `a/b/c/__init__.py` if either exists in the repo, falling back to longer prefixes. Relative imports (`from . import x`, `from ..pkg import y`) are resolved relative to the source file's directory.
- v0.2 is **Python only** by design. Multi-language call graphs ship in v0.3.

---

## [0.1.0] — 2026-05-07

### Added
- New `manifests` module — real parsing of `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`. Replaces v0.0.x's filename-only heuristics for entry-point detection.
- New `Dependency`, `DependencyGraph`, and `Conventions` data models. Schema bumped to **0.1.0**.
- New `conventions` module — light-touch convention extraction (indent style + width, src layout, tests/docs dir presence, license sniffing, known config files).
- New `languages` module — extracted language-extension and binary-extension tables for reuse.
- Language coverage extended to Java, C#, Ruby, Scala, Lua, Dart, Elixir, Erlang, Perl, R, Julia, Haskell, OCaml, Clojure, F#, Zig, Nim.
- Strict `mypy --strict` clean across all source files.
- Strict `ruff check` (E/F/W/I/B/UP/N/RUF/SIM/C4/PIE/T20) and `ruff format --check` clean.

### Changed
- Promoted from `Development Status :: 3 - Alpha` to `Development Status :: 4 - Beta`.

---

## [0.0.2] — 2026-05-05

### Fixed
- Entry-point dedup: `package.json:main` declarations no longer double-fire with the conventional-name detection.
- Migrated `datetime.utcnow()` -> `datetime.now(timezone.utc)`.
- Migrated `pathspec.PathSpec.from_lines("gitwildmatch", ...)` -> `("gitignore", ...)`.

### Verified
- 12 tests passing on Python 3.14.2, Windows. 0 warnings.

---

## [0.0.1] — 2026-05-05

### Added
- Initial scaffold: `repox` Python package with three CLI commands (`build`, `version`, `info`).
- `analyzer` module: directory walk honoring `.gitignore` via pathspec, language detection by extension, lightweight entry-point detection.
- `output` module: JSON and Markdown writers emitting to `.repox/architecture.{json,md}`.
- Pydantic v2 data models with versioned schema (initial schema 0.0.1).
- 11 smoke tests covering analyzer behavior, both writers, and CLI commands.
- Apache-2.0 license, hatchling build, typer/rich/pydantic/pathspec dependencies.

[0.3.0]: https://github.com/AbdullahBakir97/repox/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/AbdullahBakir97/repox/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/AbdullahBakir97/repox/compare/v0.0.2...v0.1.0
[0.0.2]: https://github.com/AbdullahBakir97/repox/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/AbdullahBakir97/repox/releases/tag/v0.0.1
