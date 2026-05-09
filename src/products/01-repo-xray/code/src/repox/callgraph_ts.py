"""Tree-sitter-based extractor for JavaScript and TypeScript files.

What v0.4 captures:

  - Imports: ES6 (`import { x } from 'mod'`, `import x from 'mod'`,
    `import * as ns from 'mod'`, side-effect `import 'mod'`) and
    CommonJS (`const x = require('mod')`).
  - Symbols: top-level function declarations, class declarations,
    `const`/`let` bindings, exported variants.
  - **Call edges (NEW in v0.4):** for each call_expression that sits
    inside a function / class body, emit a CallEdge with the callee
    resolved against:
      1. the file's local function / class declarations (same-file calls)
      2. the file's imported names (`import { f } from './x'` -> f
         resolves to the file ./x.ts/.js resolves to)

JavaScript-specific limitations (intentional in v0.4):

  - Default exports: we record `import x from 'mod'` as binding `x`
    locally to whatever `mod` resolves to. We don't try to follow
    "default" through to a specific symbol; the file-level resolution
    is enough for most affecting use cases.
  - Closures + hoisting: not modeled. Two-pass resolution would catch
    forward references; v0.4 does a single AST walk and accepts the
    occasional missed edge.

Tree-sitter is required as of repox v0.3, but per-file failures never
abort the build -- we skip silently and the CallGraph is just smaller.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, cast

from repox.models import CallEdge, Import, Symbol

# Mapping extension -> tree-sitter language identifier.
_EXT_LANG: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}


def _try_resolve_ts_target(raw: str, source_posix: str, repo_files: set[str]) -> str | None:
    """Resolve a JS/TS module specifier to an in-repo file."""
    if not raw or not raw.startswith("."):
        return None
    source_dir = PurePosixPath(source_posix).parent
    cleaned = raw[2:] if raw.startswith("./") else raw
    base_path = (source_dir / cleaned).as_posix()
    if base_path in repo_files:
        return base_path
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        candidate = f"{base_path}{ext}"
        if candidate in repo_files:
            return candidate
    for index in ("index.ts", "index.tsx", "index.js", "index.jsx"):
        candidate = f"{base_path}/{index}"
        if candidate in repo_files:
            return candidate
    return None


def _node_text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] in {'"', "'", "`"} and s[-1] == s[0]:
        return s[1:-1]
    return s


def _callee_text(call_node: Any, source: bytes) -> str | None:
    """Render the callable expression of a call_expression as a dotted string.

    Examples:
      `foo()`        -> "foo"
      `obj.bar()`    -> "obj.bar"
      `a.b.c()`      -> "a.b.c"
      `(x)()`        -> None (we don't track expression-form callees)
    """
    children = call_node.children
    if not children:
        return None
    fn_node = children[0]
    if fn_node.type == "identifier":
        return _node_text(fn_node, source)
    if fn_node.type == "member_expression":
        # Walk member access chains: object.attr or object.attr.attr.
        parts: list[str] = []
        cur: Any = fn_node
        while cur is not None and cur.type == "member_expression":
            prop = cur.child_by_field_name("property")
            if prop is None or prop.type not in {"property_identifier", "identifier"}:
                return None
            parts.append(_node_text(prop, source))
            cur = cur.child_by_field_name("object")
        if cur is None:
            return None
        if cur.type == "identifier":
            parts.append(_node_text(cur, source))
            return ".".join(reversed(parts))
        return None
    return None


def extract_one(
    file_path: Path,
    repo_root: Path,
    repo_files: set[str],
    parser: Any,
) -> tuple[list[Import], list[Symbol], list[CallEdge]]:
    """Parse one JS/TS file and return (imports, symbols, edges)."""
    rel = file_path.relative_to(repo_root).as_posix()
    try:
        source = file_path.read_bytes()
    except OSError:
        return [], [], []
    try:
        tree = parser.parse(source)
    except Exception:
        return [], [], []

    imports: list[Import] = []
    symbols: list[Symbol] = []
    edges: list[CallEdge] = []

    # local-name -> in-repo target_file (built from imports + same-file
    # function/class declarations) used to resolve callees later.
    local_resolution: dict[str, str] = {}

    def add_import(raw_specifier: str, line: int, local_names: list[str]) -> None:
        spec = _strip_quotes(raw_specifier)
        if not spec:
            return
        target = _try_resolve_ts_target(spec, rel, repo_files)
        imports.append(
            Import(
                source_file=rel,
                target_module=spec,
                target_file=target,
                is_relative=spec.startswith("."),
                line=line,
            )
        )
        if target is not None:
            for name in local_names:
                local_resolution.setdefault(name, target)

    def names_from_import_clause(import_node: Any) -> list[str]:
        """Pull the locally-bound names out of an `import_statement` node."""
        out: list[str] = []
        for child in import_node.children:
            if child.type == "import_clause":
                for sub in child.children:
                    if sub.type == "identifier":
                        # `import x from 'mod'` -> default import binds `x`
                        out.append(_node_text(sub, source))
                    elif sub.type == "namespace_import":
                        # `import * as ns from 'mod'` -> binds `ns`
                        for ns_child in sub.children:
                            if ns_child.type == "identifier":
                                out.append(_node_text(ns_child, source))
                    elif sub.type == "named_imports":
                        # `import { a, b as c } from 'mod'` -> binds a, c
                        for spec in sub.children:
                            if spec.type == "import_specifier":
                                alias = spec.child_by_field_name("alias")
                                name = spec.child_by_field_name("name")
                                target = alias if alias is not None else name
                                if target is not None and target.type == "identifier":
                                    out.append(_node_text(target, source))
        return out

    def walk_for_imports(node: Any) -> None:
        ntype = node.type
        if ntype == "import_statement":
            spec_str = ""
            for child in node.children:
                if child.type == "string":
                    spec_str = _node_text(child, source)
                    break
            if spec_str:
                add_import(
                    spec_str,
                    node.start_point[0] + 1,
                    names_from_import_clause(node),
                )
        elif ntype == "call_expression":
            children = node.children
            if children and children[0].type == "identifier":
                fname = _node_text(children[0], source)
                if fname == "require" and len(children) >= 2:
                    args = children[1]
                    for arg in args.children:
                        if arg.type == "string":
                            # CommonJS: `const x = require('mod')` -- the
                            # binding is the variable_declarator's name. We
                            # don't try to track that here; just record the
                            # import row so the dependency graph is honest.
                            add_import(
                                _node_text(arg, source),
                                node.start_point[0] + 1,
                                [],
                            )
                            break
        for child in node.children:
            walk_for_imports(child)

    def walk_top_level_symbols(root: Any) -> None:
        for child in root.children:
            ctype = child.type
            line = child.start_point[0] + 1
            if ctype == "function_declaration":
                name_node = child.child_by_field_name("name")
                if name_node is not None:
                    name = _node_text(name_node, source)
                    symbols.append(
                        Symbol(
                            name=name,
                            kind="function",
                            source_file=rel,
                            line=line,
                            is_public=not name.startswith("_"),
                        )
                    )
                    local_resolution.setdefault(name, rel)
            elif ctype == "class_declaration":
                name_node = child.child_by_field_name("name")
                if name_node is not None:
                    name = _node_text(name_node, source)
                    symbols.append(
                        Symbol(
                            name=name,
                            kind="class",
                            source_file=rel,
                            line=line,
                            is_public=not name.startswith("_"),
                        )
                    )
                    local_resolution.setdefault(name, rel)
            elif ctype == "export_statement":
                for sub in child.children:
                    if sub.type == "function_declaration":
                        nn = sub.child_by_field_name("name")
                        if nn is not None:
                            name = _node_text(nn, source)
                            symbols.append(
                                Symbol(
                                    name=name,
                                    kind="function",
                                    source_file=rel,
                                    line=sub.start_point[0] + 1,
                                    is_public=True,
                                )
                            )
                            local_resolution.setdefault(name, rel)
                    elif sub.type == "class_declaration":
                        nn = sub.child_by_field_name("name")
                        if nn is not None:
                            name = _node_text(nn, source)
                            symbols.append(
                                Symbol(
                                    name=name,
                                    kind="class",
                                    source_file=rel,
                                    line=sub.start_point[0] + 1,
                                    is_public=True,
                                )
                            )
                            local_resolution.setdefault(name, rel)
                    elif sub.type in {"lexical_declaration", "variable_declaration"}:
                        for var_decl in sub.children:
                            if var_decl.type == "variable_declarator":
                                nm = var_decl.child_by_field_name("name")
                                if nm is not None and nm.type == "identifier":
                                    nm_text = _node_text(nm, source)
                                    symbols.append(
                                        Symbol(
                                            name=nm_text,
                                            kind="variable",
                                            source_file=rel,
                                            line=var_decl.start_point[0] + 1,
                                            is_public=True,
                                        )
                                    )
            elif ctype in {"lexical_declaration", "variable_declaration"}:
                for var_decl in child.children:
                    if var_decl.type == "variable_declarator":
                        nm = var_decl.child_by_field_name("name")
                        if nm is not None and nm.type == "identifier":
                            nm_text = _node_text(nm, source)
                            symbols.append(
                                Symbol(
                                    name=nm_text,
                                    kind="variable",
                                    source_file=rel,
                                    line=var_decl.start_point[0] + 1,
                                    is_public=not nm_text.startswith("_"),
                                )
                            )

    def walk_for_edges(node: Any, caller_stack: list[str]) -> None:
        ntype = node.type
        # Push function / class / method names when entering a scope.
        pushed = False
        if ntype in {
            "function_declaration",
            "method_definition",
            "class_declaration",
        }:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                caller_stack.append(_node_text(name_node, source))
                pushed = True

        if ntype == "call_expression" and caller_stack:
            callee_name = _callee_text(node, source)
            if callee_name is not None:
                first_segment = callee_name.split(".", 1)[0]
                target_file = local_resolution.get(first_segment)
                edges.append(
                    CallEdge(
                        source_file=rel,
                        caller=".".join(caller_stack),
                        callee_name=callee_name,
                        target_file=target_file,
                        line=node.start_point[0] + 1,
                    )
                )

        for child in node.children:
            walk_for_edges(child, caller_stack)

        if pushed:
            caller_stack.pop()

    walk_for_imports(tree.root_node)
    walk_top_level_symbols(tree.root_node)
    walk_for_edges(tree.root_node, [])

    return imports, symbols, edges


def extract_all(
    repo_root: Path,
    ts_paths: list[str],
    repo_files: set[str],
) -> tuple[list[Import], list[Symbol], list[CallEdge]]:
    """Build parsers per language, walk every JS/TS file, return aggregates."""
    from tree_sitter import Parser
    from tree_sitter_language_pack import get_language

    parsers: dict[str, Any] = {}

    def parser_for(ext: str) -> Any | None:
        lang_id = _EXT_LANG.get(ext)
        if lang_id is None:
            return None
        if lang_id not in parsers:
            try:
                parsers[lang_id] = Parser(get_language(cast(Any, lang_id)))
            except Exception:
                return None
        return parsers[lang_id]

    all_imports: list[Import] = []
    all_symbols: list[Symbol] = []
    all_edges: list[CallEdge] = []

    for rel in ts_paths:
        path = repo_root / rel
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        parser = parser_for(ext)
        if parser is None:
            continue
        try:
            imports, symbols, edges = extract_one(path, repo_root, repo_files, parser)
        except Exception:
            continue
        all_imports.extend(imports)
        all_symbols.extend(symbols)
        all_edges.extend(edges)

    return all_imports, all_symbols, all_edges
