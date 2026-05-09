# Repo X-ray

> One artifact. Every AI tool understands your repo the same way.

Repo X-ray analyzes a codebase and produces a single, structured architecture artifact (`.repox/architecture.json` + `.repox/architecture.md`) that any AI tool can consume — Cursor, Claude Code, Copilot, custom agents, or downstream DevTrust products.

For the full product spec, see [`../PRODUCT.md`](../PRODUCT.md).

---

## v0.0.1 — what works today

- `repox build [PATH]` — walks a repo, classifies files by language, identifies likely entry points, emits both `architecture.json` and `architecture.md`.
- `repox version` — prints the installed version.
- Honors `.gitignore` via [pathspec](https://pypi.org/project/pathspec/).
- Beautiful terminal output via [rich](https://rich.readthedocs.io/).

## Roadmap (matches the master plan)

- **v0.1** — language coverage extends to TS/JS, Python, Go, Rust; basic dependency graph from manifests; convention extraction (naming patterns, error handling).
- **v0.2** — call graph via tree-sitter; module-boundary inference.
- **v0.3** — incremental updates (`repox update`); MCP server.
- **v0.5** — public release with CI integration (GitHub Action).
- **v1.0** — stable artifact format, language coverage to Java, C#, Ruby.

## Install

From the monorepo root:

```powershell
# uv (recommended) — installs all workspace members
uv sync --all-groups

# pip
pip install -e .
```

## Use

```powershell
# Analyze the current directory
repox build

# Analyze a specific repo
repox build C:\Users\you\some-repo

# Print version
repox version
```

Output lands in `.repox/architecture.json` and `.repox/architecture.md` at the analyzed repo root.

## Layout

```
code/
├── pyproject.toml
├── README.md
├── src/
│   └── repox/
│       ├── __init__.py
│       ├── __main__.py        Allows `python -m repox`
│       ├── cli.py             Typer-based CLI entry point
│       ├── models.py          Pydantic data models (Architecture, FileInfo, etc.)
│       ├── analyzer.py        Tree walk, language detection, entry-point detection
│       └── output.py          JSON + Markdown writers
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_smoke.py
```

## License

Apache-2.0. See `LICENSE` at the monorepo root.
