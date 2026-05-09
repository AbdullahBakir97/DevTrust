"""AI-quality rule pack. Two flavors:

  1. `ai-review:hallucinated-symbol` is **deterministic** -- it walks
     the call graph from a repox v0.3+ artifact and flags function
     calls whose callee name doesn't resolve to:
        - an in-repo Symbol (target_file is set), OR
        - one of the file's imported aliases (handles `from x import f`,
          `import os.path` -> "os", `import { foo } from './x'`), OR
        - a Python built-in / well-known stdlib root, OR
        - a JS/TS global / well-known npm root (when the source file
          is `.js` / `.jsx` / `.ts` / `.tsx` / `.mjs` / `.cjs`).

     Result: high-confidence "this name doesn't exist anywhere apparent
     in the codebase" signal -- exactly the AI-hallucination shape we
     want to catch in PR review.

     v0.2.0: extended to JS/TS via repox v0.4 call edges. The
     deterministic checker is language-aware -- it reads the source
     file's extension and applies the matching known-names allowlist.
     Python and JS/TS allowlists are disjoint by intent so a JS file
     calling `os.path.join` (i.e. wrong language) still flags.

  2. `ai-review:diff-comprehension` delegates to an `LLMProvider`. The
     provider receives the diff + PR description and returns its own
     findings. v0.1.0 ships the deterministic rule only; v0.1.1 wired
     in a real Anthropic backend; v0.2.0 left this rule unchanged.

Both rules are **opt-in**: the engine only invokes this module when the
caller passes `enable_ai=True`. Default-off keeps the deterministic
rule pack from depending on artifact availability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from apr.llm import LLMProvider, NullProvider
from apr.models import Finding
from apr.repox_integration import RepoxArtifact

Language = Literal["py", "js", "unknown"]

# Extensions that trigger the JS/TS allowlist. Mirrors apr.rules_js
# and repox.callgraph_ts.
_JS_EXTS: frozenset[str] = frozenset({".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})
_PY_EXTS: frozenset[str] = frozenset({".py", ".pyi"})


def _lang_for_file(rel_path: str) -> Language:
    """Infer language from a repo-relative path. POSIX-style or backslash both fine."""
    if "." not in rel_path:
        return "unknown"
    ext = "." + rel_path.rsplit(".", 1)[-1].lower()
    if ext in _JS_EXTS:
        return "js"
    if ext in _PY_EXTS:
        return "py"
    return "unknown"


# Names that are safe to call without resolving in-repo. Built-ins,
# stdlib root packages, and common third-party root names.
_KNOWN_NAMES_PY: frozenset[str] = frozenset(
    # Common Python built-ins (subset of builtins.__dict__)
    {
        "abs",
        "all",
        "any",
        "ascii",
        "bin",
        "bool",
        "bytearray",
        "bytes",
        "callable",
        "chr",
        "classmethod",
        "compile",
        "complex",
        "delattr",
        "dict",
        "dir",
        "divmod",
        "enumerate",
        "eval",
        "exec",
        "exit",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "globals",
        "hasattr",
        "hash",
        "help",
        "hex",
        "id",
        "input",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "locals",
        "map",
        "max",
        "memoryview",
        "min",
        "next",
        "object",
        "oct",
        "open",
        "ord",
        "pow",
        "print",
        "property",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "setattr",
        "slice",
        "sorted",
        "staticmethod",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "vars",
        "zip",
        # Common dunders that appear in attribute calls
        "__init__",
        "__call__",
        "__enter__",
        "__exit__",
    }
    # Common stdlib roots
    | {
        "os",
        "sys",
        "io",
        "re",
        "json",
        "csv",
        "ast",
        "math",
        "random",
        "itertools",
        "functools",
        "collections",
        "datetime",
        "time",
        "pathlib",
        "logging",
        "subprocess",
        "shutil",
        "tempfile",
        "argparse",
        "typing",
        "dataclasses",
        "enum",
        "abc",
        "warnings",
        "contextlib",
        "copy",
        "string",
        "textwrap",
        "unittest",
        "asyncio",
        "concurrent",
        "threading",
        "multiprocessing",
        "queue",
        "socket",
        "http",
        "urllib",
        "email",
        "smtplib",
        "hashlib",
        "hmac",
        "secrets",
        "uuid",
        "base64",
        "binascii",
        "struct",
        "pickle",
        "shelve",
        "sqlite3",
        "tomllib",
        "configparser",
    }
    # Common third-party roots (Python ecosystem). Conservative list.
    | {
        "numpy",
        "pandas",
        "scipy",
        "matplotlib",
        "sklearn",
        "torch",
        "tensorflow",
        "jax",
        "transformers",
        "anthropic",
        "openai",
        "fastapi",
        "starlette",
        "uvicorn",
        "flask",
        "django",
        "sqlalchemy",
        "pydantic",
        "httpx",
        "requests",
        "aiohttp",
        "boto3",
        "click",
        "typer",
        "rich",
        "tqdm",
        "pytest",
        "hypothesis",
        "redis",
        "celery",
        "psycopg",
        "asyncpg",
        "pymongo",
        "motor",
        "elasticsearch",
        "kafka",
        "pulsar",
        "ray",
        "prefect",
        "dagster",
        "airflow",
        "dbt",
        "polars",
        "duckdb",
        "pyarrow",
        "pyyaml",
        "yaml",
        "pathspec",
        "tomlkit",
        "tree_sitter",
        "jwt",
        # apr / repox / sts itself - avoid self-flagging.
        "apr",
        "repox",
        "sts",
        "sts_app",
    }
    # Common parameter / receiver names
    | {"self", "cls"}
)


# JS/TS globals + popular npm package roots. Disjoint from the Python
# allowlist by design: a `.ts` file calling `os.path.join` should still
# flag because that's a real "wrong-language hallucination" signal.
_KNOWN_NAMES_JS: frozenset[str] = frozenset(
    # ECMAScript built-ins / global objects
    {
        "Array",
        "ArrayBuffer",
        "AsyncFunction",
        "AsyncGenerator",
        "Atomics",
        "BigInt",
        "BigInt64Array",
        "BigUint64Array",
        "Boolean",
        "DataView",
        "Date",
        "Error",
        "EvalError",
        "Float32Array",
        "Float64Array",
        "Function",
        "Generator",
        "Infinity",
        "Int16Array",
        "Int32Array",
        "Int8Array",
        "Intl",
        "JSON",
        "Map",
        "Math",
        "NaN",
        "Number",
        "Object",
        "Promise",
        "Proxy",
        "RangeError",
        "ReferenceError",
        "Reflect",
        "RegExp",
        "Set",
        "String",
        "Symbol",
        "SyntaxError",
        "TypeError",
        "URIError",
        "Uint16Array",
        "Uint32Array",
        "Uint8Array",
        "Uint8ClampedArray",
        "WeakMap",
        "WeakRef",
        "WeakSet",
        "decodeURI",
        "decodeURIComponent",
        "encodeURI",
        "encodeURIComponent",
        "globalThis",
        "isFinite",
        "isNaN",
        "parseFloat",
        "parseInt",
        "structuredClone",
        "undefined",
        # Receiver names that show up as the head of method calls
        "this",
        "super",
    }
    # Browser globals
    | {
        "AbortController",
        "Blob",
        "FileReader",
        "FormData",
        "Headers",
        "Request",
        "Response",
        "URL",
        "URLSearchParams",
        "WebSocket",
        "Worker",
        "addEventListener",
        "alert",
        "atob",
        "btoa",
        "cancelAnimationFrame",
        "clearInterval",
        "clearTimeout",
        "confirm",
        "console",
        "crypto",
        "customElements",
        "document",
        "fetch",
        "history",
        "indexedDB",
        "localStorage",
        "location",
        "matchMedia",
        "navigator",
        "performance",
        "postMessage",
        "prompt",
        "queueMicrotask",
        "removeEventListener",
        "requestAnimationFrame",
        "screen",
        "sessionStorage",
        "setInterval",
        "setTimeout",
        "window",
    }
    # Node.js globals + CommonJS/ESM machinery
    | {
        "Buffer",
        "__dirname",
        "__filename",
        "exports",
        "global",
        "module",
        "process",
        "require",
    }
    # Popular npm package roots (kept conservative; falsy negatives are
    # preferable to noisy false positives in PR review).
    | {
        # React + framework family
        "React",
        "react",
        "react-dom",
        "react-native",
        "react-router",
        "react-router-dom",
        "next",
        "nextjs",
        "vue",
        "Vue",
        "angular",
        "svelte",
        "solid-js",
        "preact",
        "remix",
        "astro",
        "qwik",
        # State / data
        "redux",
        "zustand",
        "jotai",
        "recoil",
        "mobx",
        "swr",
        "axios",
        "graphql",
        "apollo",
        # Server frameworks
        "express",
        "koa",
        "fastify",
        "hapi",
        "nest",
        "hono",
        # Test / build / dev
        "jest",
        "vitest",
        "mocha",
        "chai",
        "sinon",
        "playwright",
        "cypress",
        "puppeteer",
        "storybook",
        "webpack",
        "vite",
        "rollup",
        "esbuild",
        "babel",
        "tsc",
        "eslint",
        "prettier",
        "tslib",
        "typescript",
        # Utilities
        "lodash",
        "underscore",
        "ramda",
        "rxjs",
        "dayjs",
        "moment",
        "luxon",
        "uuid",
        "zod",
        "yup",
        "joi",
        "ajv",
        "chalk",
        "commander",
        "yargs",
        "minimist",
        "debug",
        # I/O / network
        "ws",
        "socket",
        "io",
        "got",
        "node-fetch",
        # Database / ORM
        "prisma",
        "mongoose",
        "sequelize",
        "typeorm",
        "knex",
        "pg",
        "mysql",
        "mysql2",
        "sqlite3",
        "redis",
        "ioredis",
        "drizzle",
        # Auth / crypto
        "jsonwebtoken",
        "bcrypt",
        "passport",
        "argon2",
        # Cloud SDKs
        "aws-sdk",
        "googleapis",
        # apr / repox itself, in case a JS test calls into them
        "apr",
        "repox",
    }
)


def _allowed_names_for(lang: Language) -> frozenset[str]:
    """Return the known-names set the rule should consult for `lang`."""
    if lang == "py":
        return _KNOWN_NAMES_PY
    if lang == "js":
        return _KNOWN_NAMES_JS
    # Unknown language: be conservative and accept either set so we
    # don't generate noisy findings on filetypes we don't fully model.
    return _KNOWN_NAMES_PY | _KNOWN_NAMES_JS


def _check_hallucinated_symbols(
    artifact: RepoxArtifact,
    changed_files: list[str],
) -> list[Finding]:
    """Walk repox edges for changed files and flag suspicious callees.

    Cross-language: dispatches the known-names allowlist by source file
    extension so JS/TS code is checked against JS globals + npm roots
    rather than Python builtins.
    """
    out: list[Finding] = []
    changed_set = set(changed_files)

    for edge in artifact.edges:
        source_file = edge["source_file"]
        if not isinstance(source_file, str):
            continue
        if source_file not in changed_set:
            continue

        target_file = edge["target_file"]
        if isinstance(target_file, str) and target_file:
            # Resolved in-repo -- definitely not hallucinated. This is
            # also what catches in-repo JS/TS imports: repox v0.4 sets
            # target_file on edges whose callee was bound by an
            # `import { x } from './y'` statement.
            continue

        callee_name = edge["callee_name"]
        if not isinstance(callee_name, str) or not callee_name:
            continue

        first_segment = callee_name.split(".", 1)[0]

        # Heuristic: single- and double-letter names are almost always
        # iteration variables, not function calls worth flagging. This
        # also silences renamed JS imports like `import _ from 'lodash'`
        # that we can't recover the binding for from the artifact alone.
        if len(first_segment) <= 2:
            continue

        # Safe lists in priority order, dispatched by source language.
        lang = _lang_for_file(source_file)
        if first_segment in _allowed_names_for(lang):
            continue
        local_imports = artifact.imports_by_source.get(source_file, [])
        if first_segment in local_imports:
            continue

        line = edge["line"]
        line_int = line if isinstance(line, int) and line >= 1 else 1
        caller = edge["caller"] if isinstance(edge["caller"], str) else "<module>"

        out.append(
            Finding(
                rule_id="ai-review:hallucinated-symbol",
                severity="warning",
                category="ai-pattern",
                message=(
                    f"`{caller}` calls `{callee_name}` but the name "
                    "doesn't resolve to an in-repo symbol or an "
                    "imported alias. Possible AI hallucination or a "
                    "missing import."
                ),
                file=source_file,
                line=line_int,
                suggestion=(
                    "Check whether the callee is defined / imported. "
                    "If it's a third-party callable, add it to the "
                    "import list explicitly."
                ),
            )
        )
    return out


def _check_diff_comprehension(
    provider: LLMProvider,
    diff: str,
    pr_title: str | None,
    pr_description: str | None,
) -> list[Finding]:
    """Delegate to the LLMProvider and tag findings with the rule_id namespace.

    We never let provider exceptions escape - a misconfigured provider
    (missing API key, network error, NotImplementedError on the v0.1.0
    Anthropic stub) should reduce to "no findings", not break review.
    """
    if isinstance(provider, NullProvider):
        return []
    try:
        raw = provider.analyze_diff(diff, pr_title, pr_description)
    except Exception:
        return []
    # Re-emit each finding under our namespace so the provider's choice
    # of rule_id doesn't leak into apr's stable ID set.
    out: list[Finding] = []
    for f in raw:
        out.append(
            Finding(
                rule_id="ai-review:diff-comprehension",
                severity=f.severity,
                category="ai-pattern",
                message=f.message,
                file=f.file,
                line=f.line,
                suggestion=f.suggestion,
            )
        )
    return out


def run_ai_rules(
    repo_root: Path,
    changed_files: list[str],
    *,
    artifact: RepoxArtifact | None,
    provider: LLMProvider,
    diff: str | None = None,
    pr_title: str | None = None,
    pr_description: str | None = None,
) -> list[Finding]:
    """Top-level entry point for the AI rule pack.

    Both rules are best-effort: a missing repox artifact silences
    hallucinated-symbol; a NullProvider silences diff-comprehension.
    Neither absence raises.
    """
    findings: list[Finding] = []

    if artifact is not None:
        findings.extend(_check_hallucinated_symbols(artifact, changed_files))

    if diff:
        findings.extend(_check_diff_comprehension(provider, diff, pr_title, pr_description))

    return findings
