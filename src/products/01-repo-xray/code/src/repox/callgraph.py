"""Per-file import + symbol + call-edge extraction for Python.

What v0.3 captures (Python via stdlib `ast`):

  - Imports: every `import X` and `from X import Y` statement, with the
    target module resolved to an in-repo file path when possible.
  - Symbols: top-level functions, classes, methods, top-level variables.
  - Call edges (NEW): for each function or method body, every
    `Call` node with the callee resolved to an imported file when
    possible.

What lives elsewhere:

  - JS / TS imports + symbols: `repox.callgraph_ts` (tree-sitter).
  - Function-call edges for JS / TS: deferred to v0.4.
"""

from __future__ import annotations

import ast
import contextlib
from pathlib import Path, PurePosixPath

from repox.models import CallEdge, CallGraph, Import, Symbol

# ---------------------------------------------------------------------------
# import target resolution
# ---------------------------------------------------------------------------


def _try_resolve(base: str, repo_files: set[str]) -> str | None:
    """Look for `base.py` then `base/__init__.py`. Empty base means repo root."""
    if not base:
        candidate = "__init__.py"
        return candidate if candidate in repo_files else None
    for c in (f"{base}.py", f"{base}/__init__.py"):
        if c in repo_files:
            return c
    return None


def _resolve_python_target(
    raw_module: str,
    is_relative: bool,
    relative_level: int,
    imported_names: list[str],
    source_posix: str,
    repo_files: set[str],
) -> str | None:
    """Resolve the imported target to an in-repo file path, or None."""
    if is_relative:
        source_dir = PurePosixPath(source_posix).parent
        for _ in range(max(0, relative_level - 1)):
            source_dir = source_dir.parent
        if raw_module:
            base = (source_dir / raw_module.replace(".", "/")).as_posix()
        else:
            base = source_dir.as_posix() if str(source_dir) != "." else ""
    else:
        base = raw_module.replace(".", "/")

    # 1) <base>/<imported_name>.py for each imported name.
    if imported_names:
        for name in imported_names:
            sub_base = f"{base}/{name}" if base else name
            resolved = _try_resolve(sub_base, repo_files)
            if resolved is not None:
                return resolved

    # 2) Fall back to base itself.
    resolved = _try_resolve(base, repo_files)
    if resolved is not None:
        return resolved

    # 3) For absolute imports, walk parent prefixes.
    if not is_relative:
        parts = base.split("/")
        while parts:
            parts.pop()
            partial = "/".join(parts)
            resolved = _try_resolve(partial, repo_files)
            if resolved is not None:
                return resolved
    return None


# ---------------------------------------------------------------------------
# call-edge extraction
# ---------------------------------------------------------------------------


def _callee_name_of(call: ast.Call) -> str | None:
    """Render the call's callable expression as a dotted string, or None.

    Examples: `foo()` -> "foo"; `obj.bar()` -> "obj.bar"; `a.b.c()` -> "a.b.c";
    `(lambda x: x)()` -> None (we don't track expression-form callees).
    """
    func = call.func
    parts: list[str] = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    else:
        return None
    return ".".join(reversed(parts)) if parts else None


def _build_local_resolution(
    tree: ast.Module,
    file_symbols: list[Symbol],
    source_posix: str,
    repo_files: set[str],
) -> dict[str, str]:
    """Build a map: local-name -> in-repo target_file for a single file.

    Sources of resolution (in priority order):

      1. Same-file top-level functions and classes (so direct calls
         like `helper()` resolve to this file when `helper` is defined here).
      2. `from X import name [as alias]` -- the `alias` (or `name`) binds
         locally to the file that `X.name` resolves to. We re-walk the
         AST here because the Import row only carries the module-level
         `target_file`, which can't distinguish `from x import a`
         (which binds `a`) from `from x import b` (which binds `b`)
         when `a` and `b` resolve to different files.
      3. `import X [as alias]` -- the alias (or first segment of X) binds
         locally to whatever `X` resolves to.
    """
    out: dict[str, str] = {}

    # 1. Same-file top-level functions / classes win
    for sym in file_symbols:
        if sym.kind in {"function", "class"}:
            out.setdefault(sym.name, sym.source_file)

    # 2. + 3. Re-walk imports using the actual local-binding names
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level or 0
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                target = _resolve_python_target(
                    raw_module=module,
                    is_relative=level > 0,
                    relative_level=level,
                    imported_names=[alias.name],
                    source_posix=source_posix,
                    repo_files=repo_files,
                )
                if target is not None:
                    out[local_name] = target
        elif isinstance(node, ast.Import):
            for alias in node.names:
                # `import X.Y` binds the local name `X` (the top-level package).
                # `import X.Y as Z` binds `Z`.
                local_name = alias.asname or alias.name.split(".", 1)[0]
                target = _resolve_python_target(
                    raw_module=alias.name,
                    is_relative=False,
                    relative_level=0,
                    imported_names=[],
                    source_posix=source_posix,
                    repo_files=repo_files,
                )
                if target is not None:
                    out[local_name] = target
    return out


def _walk_calls(
    tree: ast.AST,
    file_rel: str,
    local_resolution: dict[str, str],
    edges: list[CallEdge],
) -> None:
    """Walk `tree` and emit a CallEdge for each Call inside a FunctionDef body."""

    class _CallVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            qualified = ".".join([*self.stack, node.name])
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()
            _ = qualified

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if not self.stack:
                # Module-level call - we don't track these for v0.3.
                self.generic_visit(node)
                return
            callee = _callee_name_of(node)
            if callee is not None:
                first_segment = callee.split(".", 1)[0]
                target = local_resolution.get(first_segment)
                edges.append(
                    CallEdge(
                        source_file=file_rel,
                        caller=".".join(self.stack),
                        callee_name=callee,
                        target_file=target,
                        line=node.lineno,
                    )
                )
            self.generic_visit(node)

    _CallVisitor().visit(tree)


# ---------------------------------------------------------------------------
# top-level extractors
# ---------------------------------------------------------------------------


def extract_python(
    file_path: Path, repo_root: Path, repo_files: set[str]
) -> tuple[list[Import], list[Symbol], list[CallEdge]]:
    """Parse one Python file and return (imports, symbols, edges).

    Errors (syntax errors, encoding issues, IO errors) are swallowed and
    the function returns ([], [], []). repox NEVER fails a build because
    of one bad source file.
    """
    rel = file_path.relative_to(repo_root).as_posix()
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=rel)
    except (OSError, SyntaxError, ValueError):
        return [], [], []

    imports: list[Import] = []
    symbols: list[Symbol] = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve_python_target(
                    raw_module=alias.name,
                    is_relative=False,
                    relative_level=0,
                    imported_names=[],
                    source_posix=rel,
                    repo_files=repo_files,
                )
                imports.append(
                    Import(
                        source_file=rel,
                        target_module=alias.name,
                        target_file=target,
                        is_relative=False,
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level or 0
            names = [a.name for a in node.names if a.name != "*"]
            target = _resolve_python_target(
                raw_module=module,
                is_relative=level > 0,
                relative_level=level,
                imported_names=names,
                source_posix=rel,
                repo_files=repo_files,
            )
            imports.append(
                Import(
                    source_file=rel,
                    target_module=("." * level) + module,
                    target_file=target,
                    is_relative=level > 0,
                    line=node.lineno,
                )
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            symbols.append(
                Symbol(
                    name=node.name,
                    kind="function",
                    source_file=rel,
                    line=node.lineno,
                    is_public=not node.name.startswith("_"),
                )
            )
        elif isinstance(node, ast.ClassDef):
            symbols.append(
                Symbol(
                    name=node.name,
                    kind="class",
                    source_file=rel,
                    line=node.lineno,
                    is_public=not node.name.startswith("_"),
                )
            )
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef):
                    symbols.append(
                        Symbol(
                            name=f"{node.name}.{sub.name}",
                            kind="method",
                            source_file=rel,
                            line=sub.lineno,
                            is_public=not sub.name.startswith("_"),
                        )
                    )
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    symbols.append(
                        Symbol(
                            name=tgt.id,
                            kind="variable",
                            source_file=rel,
                            line=node.lineno,
                            is_public=not tgt.id.startswith("_"),
                        )
                    )

    # Walk the AST to extract function-call edges. The local-name
    # resolution map binds each `from X import Y as Z` (or plain `import X`)
    # to the file that target resolves to.
    local_resolution = _build_local_resolution(tree, symbols, rel, repo_files)
    edges: list[CallEdge] = []
    _walk_calls(tree, rel, local_resolution, edges)

    return imports, symbols, edges


def extract(repo_root: Path, file_paths: list[str]) -> CallGraph | None:
    """Walk every Python file (and JS/TS file via callgraph_ts) and return
    a populated CallGraph."""
    py_paths = [p for p in file_paths if p.endswith(".py")]
    ts_paths = [p for p in file_paths if p.endswith((".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"))]
    if not py_paths and not ts_paths:
        return None

    repo_set: set[str] = set(file_paths)
    all_imports: list[Import] = []
    all_symbols: list[Symbol] = []
    all_edges: list[CallEdge] = []

    for rel in py_paths:
        path = repo_root / rel
        if not path.is_file():
            continue
        with contextlib.suppress(Exception):
            imports, symbols, edges = extract_python(path, repo_root, repo_set)
            all_imports.extend(imports)
            all_symbols.extend(symbols)
            all_edges.extend(edges)

    # Tree-sitter-based JS / TS extraction is best-effort - if the
    # tree-sitter wheels aren't available, we skip silently and the
    # CallGraph just lacks JS / TS data.
    if ts_paths:
        try:
            from repox import callgraph_ts as ts_mod

            ts_imports, ts_symbols, ts_edges = ts_mod.extract_all(repo_root, ts_paths, repo_set)
            all_imports.extend(ts_imports)
            all_symbols.extend(ts_symbols)
            all_edges.extend(ts_edges)
        except Exception:  # broad on purpose: tree-sitter is optional
            pass

    return CallGraph(
        imports=all_imports,
        symbols=all_symbols,
        edges=all_edges,
    )
