# Definition of Done — DevTrust quality bar

> Every DevTrust product must hit every checkbox below before its version is considered shipped, regardless of which wave or build phase it sits in. This file is the *contract* that turns "professional" from a feeling into a checklist.

This DOD has three tiers. The version a product is at determines which tier applies.

| Tier | Versions | Use |
|---|---|---|
| **A · Scaffold** | v0.0.x | First runnable code; smoke tests; happy-path only |
| **B · Beta** | v0.1 – v0.5 | Full feature set per spec; broad test coverage; CI; docs |
| **C · Release** | v1.0+ | Hardened; security-reviewed; benchmarked; production-ready; signed releases |

---

## Tier A — Scaffold (v0.0.x)

Repo X-ray's v0.0.2 hits this tier. Every product passes through it on the way to Tier B.

### Code structure
- [ ] Standard `src/<package>/` layout under `src/products/NN-name/code/`
- [ ] `pyproject.toml` with hatchling build, license, classifiers, scripts entry, deps pinned to ranges (`>=` not `==`)
- [ ] Package has `__init__.py` exporting `__version__` matching `pyproject.toml`
- [ ] `__main__.py` enables `python -m <package>` invocation
- [ ] Public API surface lives in well-named modules, not in `cli.py`

### Tests
- [ ] `tests/` directory with `conftest.py` fixtures
- [ ] At least one smoke test covering the happy path of every public CLI command
- [ ] Tests run cleanly via `pytest` from the repo root with **0 warnings** (Python 3.14 is strict)

### Docs
- [ ] Per-product `README.md` with: install, quickstart (under 5 lines of commands), feature list for the current version, link back to `PRODUCT.md` spec
- [ ] `PRODUCT.md` exists and is up to date

### Hygiene
- [ ] Code passes `ruff check` and `ruff format --check`
- [ ] Imports are sorted (ruff handles this)
- [ ] No stray `print()` calls outside CLI output paths
- [ ] No TODO comments without an associated task in `TASKS.md`

---

## Tier B — Beta (v0.1 – v0.5)

This is where most of DevTrust's products will live during build mode.

### Everything from Tier A, plus:

### Code completeness
- [ ] **All MVP features** listed in the product's `PRODUCT.md` are implemented
- [ ] No `NotImplementedError` raised by any code path the user can hit
- [ ] All Pydantic models / data structures exposed publicly are versioned (e.g. `SCHEMA_VERSION` in repox)
- [ ] Errors are typed (custom exception classes), not bare `Exception`
- [ ] Every public function has a docstring

### Type safety
- [ ] `mypy --strict` passes on the entire `src/` of the package
- [ ] No `# type: ignore` comments without a paired explanation comment
- [ ] No `Any` in public function signatures (private internals may use it sparingly)

### Tests
- [ ] **Unit tests** covering every public function in the package
- [ ] **Integration tests** covering every CLI command with at least one happy path and one error path
- [ ] **Regression tests** for every bug fixed in this product (named `test_regression_<bug>`)
- [ ] Test coverage **>= 85%** (measured by `pytest --cov`)
- [ ] Tests run on Windows AND Linux (via CI matrix)

### CI
- [ ] GitHub Actions workflow at `.github/workflows/ci.yml` that runs:
  - Ruff check + format check
  - Mypy strict
  - Pytest with coverage on Python 3.11, 3.12, 3.13, 3.14
  - On Ubuntu, Windows, macOS
- [ ] CI runs on every push to `main` and every pull request
- [ ] CI status badge in the product's README

### Docs
- [ ] `CHANGELOG.md` with entries for every version since scaffold (Keep-a-Changelog format)
- [ ] `README.md` includes: feature highlights, install, quickstart, full CLI reference, examples, FAQ, contributing, license
- [ ] If the product exposes an API/schema (Repo X-ray, Agent Trace SDK), the schema is documented in a dedicated `SCHEMA.md`
- [ ] At least 3 worked examples in `examples/` directory

### Hygiene
- [ ] `pre-commit` config installed: ruff, mypy, conventional-commits hook, end-of-file-fixer, trailing-whitespace
- [ ] LICENSE file present and matches the lane in master plan (Apache-2.0 for OSS lane)
- [ ] CONTRIBUTING.md present with dev setup steps
- [ ] CODE_OF_CONDUCT.md present (Contributor Covenant v3.0)
- [ ] `.editorconfig` present
- [ ] Issue and PR templates in `.github/`

---

## Tier C — Release (v1.0+)

This is the bar before any product is published publicly (PyPI, GitHub Releases, npm, crates.io, etc.).

### Everything from Tier B, plus:

### Hardening
- [ ] Security review of dependencies via `pip-audit` (and `cargo-audit` / `npm audit` where relevant) — clean
- [ ] Static analysis with bandit or equivalent — clean
- [ ] Fuzz tests for parsing-heavy components (e.g. Repo X-ray's manifest parsers)
- [ ] All user-supplied input is validated and sanitized at boundaries (CLI args, config files, network input)
- [ ] All file I/O uses safe-path resolution (no path traversal)
- [ ] Secrets handling is documented; secrets never logged

### Performance
- [ ] At least one published benchmark for the dominant operation (e.g. Repo X-ray: time to analyze a 100K-LOC repo)
- [ ] Memory profile for the dominant operation captured
- [ ] No O(n²) hot paths on inputs that scale with repo / customer size

### Observability
- [ ] Structured logging using stdlib `logging` (with a module-level logger named after the package)
- [ ] Log levels appropriate (DEBUG, INFO, WARNING, ERROR)
- [ ] Optional `--verbose` and `--quiet` flags wired through to log config
- [ ] When the product emits its own telemetry (RUN-line products), it uses Agent Trace SDK

### Release infrastructure
- [ ] Tagged release (`v1.0.0`) on GitHub
- [ ] Signed git tag (GPG or sigstore)
- [ ] Release notes generated and published
- [ ] Package published to its target registry (PyPI for Python; appropriate registry for others)
- [ ] Package signed (Sigstore for PyPI / cosign for containers)

### Docs site
- [ ] Hosted documentation (mkdocs or sphinx); landing page; tutorial; reference
- [ ] At least 3 case studies (anonymized at first if no design partners; replace with real once shipped)
- [ ] Migration guide from v0.x to v1.0 if any breaking changes

### Operational
- [ ] Issue triage process documented
- [ ] Security reporting policy in `SECURITY.md`
- [ ] Backup/recovery procedures for any state the product manages

---

## How to use this document

1. When starting work on a product, **decide which tier you're targeting** for this session's version bump.
2. Open this DOD alongside the product's `PRODUCT.md`.
3. Walk the tier's checklist top to bottom — no item gets skipped without a written reason in the product's `CHANGELOG.md`.
4. Only after all boxes are ticked: bump version, commit, move to the next product in `BUILD-QUEUE.md`.

This document is **versioned**. When the team decides to raise the bar, edit this file, commit, and apply the new bar to the next version of every product. Don't retroactively fail products that were green at a prior bar.

DOD version: **1.0** · 2026-05-05
