"""Optional integration with Repo X-ray.

When `.repox/architecture.json` exists at the repo root, apr can read
its `call_graph.imports` and `call_graph.edges` arrays to power
ai-review:* rules that reason about whether a called symbol actually
exists in the repo.

Same shape as sts's repox_integration: best-effort loader that returns
None on missing/malformed/missing-call-graph artifacts.

v0.2.0: the binding-hint extractor (`_binding_hint`) is now
language-aware so JS/TS imports like `react-dom/client`, `@scope/pkg`,
or bare `'express'` produce a usable binding name for the
hallucinated-symbol rule's allowlist check.
"""

from __future__ import annotations

import json
from pathlib import Path

from apr.models import Finding  # noqa: F401  -- used by re-exports


def _binding_hint(target_module: str) -> str | None:
    """Best-effort guess of the local binding a `target_module` introduces.

    The artifact carries the module specifier but not the `import`
    clause's actual local name(s), so this is necessarily heuristic.
    Choices:

      Python:
        - `os`            -> "os"
        - `os.path`       -> "path"   (last dotted segment)
        - `..rel.helpers` -> "helpers"
      JS / TS:
        - `react`             -> "react"
        - `react-dom`         -> "react-dom"
        - `react-dom/client`  -> "client"  (last slash segment)
        - `@scope/pkg`        -> "pkg"
        - `@scope/pkg/sub`    -> "sub"
      Relative JS/TS paths (`./x`, `../x`):
        - returns None -- the binding can only come from the import
          clause we don't see. Fortunately repox v0.4 already resolves
          those paths on the call edge itself (`target_file`), so the
          rule's "target_file is set -> skip" short-circuit handles
          them without needing the binding hint.
    """
    if not target_module:
        return None
    m = target_module.strip()
    if not m:
        return None
    # JS/TS relative path -- no binding info we can infer.
    if m in {".", ".."} or m.startswith(("./", "../")):
        return None
    # JS/TS scoped or path-style: prefer the last slash segment.
    if "/" in m or m.startswith("@"):
        last = m.rsplit("/", 1)[-1]
        return last or None
    # Python dotted: prefer the last dotted segment.
    if "." in m:
        # Strip leading dots first ('..rel.helpers' -> 'rel.helpers').
        cleaned = m.lstrip(".")
        if not cleaned:
            return None
        last = cleaned.rsplit(".", 1)[-1]
        return last or None
    # Bare name -- works for `import os` (Py) or `import x from 'react'` (JS).
    return m


def architecture_path(repo_root: Path) -> Path:
    """Canonical path of repox's JSON artifact at this repo root."""
    return repo_root / ".repox" / "architecture.json"


class RepoxArtifact:
    """Parsed subset of repox's architecture.json that apr reasons about.

    We don't use Pydantic here because the only consumer is the rules
    module and we want zero ceremony - just typed dicts.
    """

    __slots__ = (
        "edges",
        "imports_by_source",
        "tool_version",
    )

    def __init__(
        self,
        edges: list[dict[str, object]],
        imports_by_source: dict[str, list[str]],
        tool_version: str,
    ) -> None:
        self.edges = edges
        self.imports_by_source = imports_by_source
        self.tool_version = tool_version


def load(repo_root: Path) -> RepoxArtifact | None:
    """Try to load and parse .repox/architecture.json.

    Returns None if the file is missing, malformed, or doesn't include
    a call graph (older repox versions). The caller treats None as
    "no AI rules will run" (graceful no-op).
    """
    arch_path = architecture_path(repo_root)
    if not arch_path.is_file():
        return None
    try:
        text = arch_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    cg = data.get("call_graph")
    if not isinstance(cg, dict):
        return None

    raw_edges = cg.get("edges", [])
    raw_imports = cg.get("imports", [])
    if not isinstance(raw_edges, list) or not isinstance(raw_imports, list):
        return None

    edges: list[dict[str, object]] = []
    for e in raw_edges:
        if not isinstance(e, dict):
            continue
        edges.append(
            {
                "source_file": e.get("source_file"),
                "caller": e.get("caller"),
                "callee_name": e.get("callee_name"),
                "target_file": e.get("target_file"),
                "line": e.get("line"),
            }
        )

    imports_by_source: dict[str, list[str]] = {}
    for imp in raw_imports:
        if not isinstance(imp, dict):
            continue
        src = imp.get("source_file")
        target_module = imp.get("target_module") or ""
        if not isinstance(src, str) or not isinstance(target_module, str):
            continue
        # Each import row contributes a best-effort local-binding name.
        # The artifact doesn't carry the import clause's actual `as`
        # rename (that would require a repox schema bump), so we infer:
        #   - Python `import os.path`  -> 'path'  (last dotted segment)
        #   - JS    `import x from 'react'`        -> 'react'
        #   - JS    `import x from 'react-dom'`    -> 'react-dom'
        #   - JS    `import x from 'react-dom/client'` -> 'client'
        #   - JS    `import x from '@scope/pkg'`   -> 'pkg'
        #   - JS    `import x from './helpers'`    -> None (path-based,
        #            in-repo: repox already resolved this and set
        #            target_file on the call edge, so the rule's
        #            target_file-set short-circuit handles it).
        bare = _binding_hint(target_module)
        if bare:
            imports_by_source.setdefault(src, []).append(bare)

    tool_version = (
        data.get("tool_version") if isinstance(data.get("tool_version"), str) else "unknown"
    )

    return RepoxArtifact(
        edges=edges,
        imports_by_source=imports_by_source,
        tool_version=str(tool_version),
    )
