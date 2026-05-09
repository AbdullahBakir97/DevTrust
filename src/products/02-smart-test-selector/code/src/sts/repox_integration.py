"""Optional integration with Repo X-ray.

When `.repox/architecture.json` exists at the repo root, sts can read it
directly instead of doing its own file walk:

  - Faster: the artifact already lists every gitignore-respecting file
    in the repo, so no rglob() needed.
  - More accurate: repox respects `.gitignore`, sts's CLI walker only
    skips a small hardcoded set of dirs.
  - **Call-graph-aware affecting (new in v0.0.3):** the artifact also
    carries the import graph. sts uses this to build the reverse-import
    graph and walk it from changed files, finding every test that
    transitively imports a changed module.

If the artifact is missing, malformed, or the repox dependency isn't
installed, this module's loader returns None and the caller falls back
to its own walk. sts NEVER hard-fails because of a missing architecture.
"""

from __future__ import annotations

import json
from pathlib import Path

from sts.models import RepoxArtifact


def architecture_path(repo_root: Path) -> Path:
    """Canonical path of repox's JSON artifact at this repo root."""
    return repo_root / ".repox" / "architecture.json"


def _extract_imports_by_source(data: dict[str, object]) -> dict[str, list[str]]:
    """Pull `source_file -> [in-repo target_files]` out of an architecture JSON.

    Repox v0.2.0+ writes a `call_graph.imports` array on the artifact;
    older versions don't. Either way we return an empty dict on failure.
    """
    cg = data.get("call_graph")
    if not isinstance(cg, dict):
        return {}
    imports = cg.get("imports")
    if not isinstance(imports, list):
        return {}
    out: dict[str, list[str]] = {}
    for entry in imports:
        if not isinstance(entry, dict):
            continue
        src = entry.get("source_file")
        tgt = entry.get("target_file")
        if isinstance(src, str) and isinstance(tgt, str):
            out.setdefault(src, []).append(tgt)
    # Dedupe each source's target list (an `import x; from x import y`
    # pair would otherwise list the same target twice).
    return {k: sorted(set(v)) for k, v in out.items()}


def load_files(repo_root: Path) -> RepoxArtifact | None:
    """Try to load `.repox/architecture.json` and extract files + imports.

    Returns None if the artifact is absent or unreadable. Returns a
    populated `RepoxArtifact` on success - schema-version mismatch is
    flagged via the model's `incompatible_schema` field but does NOT
    cause a None return.
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

    raw_files = data.get("files")
    if not isinstance(raw_files, list):
        return None

    paths: list[str] = []
    for entry in raw_files:
        if isinstance(entry, dict):
            p = entry.get("path")
            if isinstance(p, str):
                paths.append(p)
        elif isinstance(entry, str):
            paths.append(entry)

    if not paths:
        return None

    imports_by_source = _extract_imports_by_source(data)

    schema = data.get("schema_version", "unknown")
    tool_v = data.get("tool_version", "unknown")
    incompatible = not (isinstance(schema, str) and schema.startswith(("0.", "1.")))

    return RepoxArtifact(
        paths=sorted(set(paths)),
        schema_version=str(schema),
        tool_version=str(tool_v),
        incompatible_schema=incompatible,
        imports_by_source=imports_by_source,
    )
