"""Pydantic models for the Repo X-ray architecture artifact.

The schema in this file *is* the public API of Repo X-ray. Every downstream
consumer (Smart Test Selector, Agent-PR Reviewer, Dep Upgrade Pilot, plus
any external AI tool) reads this shape. Treat changes to it as breaking.

Versioned via the top-level `Architecture.schema_version` field.

History
-------
- 0.0.1 - initial schema
- 0.1.0 - adds optional Architecture.dependencies (DependencyGraph) and
          Architecture.conventions (Conventions). Existing fields unchanged;
          old-version readers continue to work.
- 0.2.0 - adds optional Architecture.call_graph (CallGraph) with `Import`
          and `Symbol` rows for Python source files. Non-breaking.
- 0.3.0 - adds `CallEdge` rows on CallGraph (Python function-level call
          graph) and tree-sitter-driven JS / TS imports + symbols.
          Non-breaking - new fields are optional / additive.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Bump only when the schema breaks something downstream readers rely on.
SCHEMA_VERSION = "0.3.0"


# ---------------------------------------------------------------------------
# Files & languages
# ---------------------------------------------------------------------------


class FileInfo(BaseModel):
    """A single file in the repo."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(..., description="Path relative to repo root, POSIX-style.")
    language: str | None = Field(None, description="Detected language, or None if unknown/binary.")
    size_bytes: int = Field(..., ge=0)
    line_count: int | None = Field(
        None, ge=0, description="Line count for text files; None for binary."
    )
    is_binary: bool = False


class LanguageStats(BaseModel):
    """Aggregate stats for one language across the repo."""

    model_config = ConfigDict(frozen=True)

    name: str
    file_count: int = Field(..., ge=0)
    line_count: int = Field(..., ge=0)
    bytes: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Entry points & manifests
# ---------------------------------------------------------------------------


class EntryPoint(BaseModel):
    """A detected likely entry point (a file the program starts at)."""

    model_config = ConfigDict(frozen=True)

    path: str
    kind: str = Field(
        ...,
        description=(
            "e.g. 'package.json:main', 'pyproject:scripts', 'Cargo.toml:bin', "
            "'go:module', 'cli', 'web', 'container'."
        ),
    )
    detail: str | None = None


class ManifestInfo(BaseModel):
    """Per-manifest summary - one row per parsed manifest file."""

    model_config = ConfigDict(frozen=True)

    path: str
    kind: Literal["pyproject", "package.json", "Cargo.toml", "go.mod"]
    package_name: str | None = None
    package_version: str | None = None
    dependency_count: int = 0


# ---------------------------------------------------------------------------
# Dependencies (new in 0.1.0)
# ---------------------------------------------------------------------------

DependencyKind = Literal["runtime", "dev", "optional", "build"]


class Dependency(BaseModel):
    """A direct dependency declared in a manifest."""

    model_config = ConfigDict(frozen=True)

    name: str
    version_spec: str | None = None
    source: str = Field(..., description="The manifest filename it came from.")
    kind: DependencyKind = "runtime"


class DependencyGraph(BaseModel):
    """The repo's declared dependencies and the manifests they came from."""

    model_config = ConfigDict(frozen=False)

    manifests: list[ManifestInfo] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)

    @property
    def runtime(self) -> list[Dependency]:
        return [d for d in self.dependencies if d.kind == "runtime"]

    @property
    def dev(self) -> list[Dependency]:
        return [d for d in self.dependencies if d.kind == "dev"]

    @property
    def optional(self) -> list[Dependency]:
        return [d for d in self.dependencies if d.kind == "optional"]


# ---------------------------------------------------------------------------
# Conventions (new in 0.1.0)
# ---------------------------------------------------------------------------

IndentStyle = Literal["space", "tab", "mixed", "unknown"]


class Conventions(BaseModel):
    """Light-touch conventions extracted from observable file structure."""

    model_config = ConfigDict(frozen=False)

    primary_indent: IndentStyle = "unknown"
    indent_width: int | None = Field(default=None, ge=1, le=16)
    has_tests_dir: bool = False
    has_docs_dir: bool = False
    has_src_layout: bool = False
    primary_license: str | None = None
    config_files: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Call graph (imports + symbols in 0.2.0; edges added in 0.3.0)
# ---------------------------------------------------------------------------

SymbolKind = Literal["function", "class", "method", "variable"]


class Import(BaseModel):
    """A single `import` or `from X import Y` statement."""

    model_config = ConfigDict(frozen=True)

    source_file: str = Field(..., description="The file containing the import.")
    target_module: str = Field(
        ...,
        description=("The module name as written. Relative imports keep their dots."),
    )
    target_file: str | None = Field(
        default=None,
        description="In-repo file the module resolves to (POSIX), or None.",
    )
    is_relative: bool = False
    line: int = Field(..., ge=1)


class Symbol(BaseModel):
    """A function, class, method, or top-level variable defined in a file."""

    model_config = ConfigDict(frozen=True)

    name: str
    kind: SymbolKind
    source_file: str
    line: int = Field(..., ge=1)
    is_public: bool = True


class CallEdge(BaseModel):
    """A function-level call edge: function `caller` calls `callee_name`.

    `target_file` is set when the callee resolves unambiguously to an
    in-repo Symbol.
    """

    model_config = ConfigDict(frozen=True)

    source_file: str
    caller: str = Field(..., description="Qualified name of the calling function.")
    callee_name: str = Field(
        ...,
        description='The callable expression as written: "foo", "obj.bar", "x.y.z".',
    )
    target_file: str | None = Field(
        default=None,
        description="In-repo file the callee resolves to (POSIX), or None.",
    )
    line: int = Field(..., ge=1)


class CallGraph(BaseModel):
    """The repo's import + symbol + call-edge graph.

    v0.2.0 captures imports and top-level symbols for Python source.
    v0.3.0 adds `edges` (function-level call graph) and tree-sitter-driven
    imports + symbols for JS / TS files.
    """

    model_config = ConfigDict(frozen=False)

    imports: list[Import] = Field(default_factory=list)
    symbols: list[Symbol] = Field(default_factory=list)
    edges: list[CallEdge] = Field(default_factory=list)

    def imports_by_file(self) -> dict[str, list[str]]:
        """For each file, list the in-repo target paths it imports."""
        out: dict[str, list[str]] = {}
        for imp in self.imports:
            if imp.target_file is not None:
                out.setdefault(imp.source_file, []).append(imp.target_file)
        return out

    def files_importing(self, target: str) -> list[str]:
        """List of files that import the given in-repo target path."""
        return sorted({imp.source_file for imp in self.imports if imp.target_file == target})

    def callers_of(self, target_file: str) -> list[str]:
        """List of source files containing edges that resolve to target_file."""
        return sorted({edge.source_file for edge in self.edges if edge.target_file == target_file})


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


class RepoMeta(BaseModel):
    """Top-level repo metadata."""

    model_config = ConfigDict(frozen=True)

    name: str
    root: str
    total_files: int = Field(..., ge=0)
    total_size_bytes: int = Field(..., ge=0)
    total_lines: int = Field(..., ge=0)


class Architecture(BaseModel):
    """The full architecture artifact emitted by `repox build`.

    JSON layout: `.repox/architecture.json`
    Human-readable companion: `.repox/architecture.md`
    """

    model_config = ConfigDict(frozen=False)

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    tool_version: str

    repo: RepoMeta
    languages: list[LanguageStats]
    entry_points: list[EntryPoint]
    files: list[FileInfo]

    # Optional - new fields added in 0.1.0 / 0.2.0 / 0.3.0. Old readers ignore.
    dependencies: DependencyGraph | None = None
    conventions: Conventions | None = None
    call_graph: CallGraph | None = None

    @classmethod
    def empty(cls, root_path: str, tool_version: str) -> Architecture:
        """Construct a placeholder Architecture for an empty repo."""
        return cls(
            generated_at=datetime.now(UTC),
            tool_version=tool_version,
            repo=RepoMeta(
                name="",
                root=root_path,
                total_files=0,
                total_size_bytes=0,
                total_lines=0,
            ),
            languages=[],
            entry_points=[],
            files=[],
        )
