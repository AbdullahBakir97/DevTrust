"""Language and binary-extension tables.

Extracted from `analyzer` in v0.1 so other modules (and downstream products)
can reuse the same classification without depending on the analyzer.
"""

from __future__ import annotations

EXT_TO_LANG: dict[str, str] = {
    # systems / general purpose
    ".py": "Python",
    ".pyi": "Python",
    ".rs": "Rust",
    ".go": "Go",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".cs": "C#",
    ".fs": "F#",
    ".fsx": "F#",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".sc": "Scala",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".lua": "Lua",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".pl": "Perl",
    ".pm": "Perl",
    ".r": "R",
    ".R": "R",
    ".jl": "Julia",
    ".hs": "Haskell",
    ".lhs": "Haskell",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".clj": "Clojure",
    ".cljs": "Clojure",
    ".cljc": "Clojure",
    ".zig": "Zig",
    ".nim": "Nim",
    # web / scripting
    ".js": "JavaScript",
    ".cjs": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".astro": "Astro",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    # data / config / docs
    ".json": "JSON",
    ".jsonc": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".md": "Markdown",
    ".mdx": "Markdown",
    ".rst": "reStructuredText",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".dockerfile": "Dockerfile",
    ".tf": "Terraform",
    ".hcl": "HCL",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protobuf",
    # notebooks
    ".ipynb": "Jupyter Notebook",
}

BINARY_EXTS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".ico",
        ".svg",
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".7z",
        ".rar",
        ".xz",
        ".mp3",
        ".mp4",
        ".mov",
        ".wav",
        ".ogg",
        ".webm",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".class",
        ".jar",
        ".war",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".pyc",
        ".pyo",
    }
)

# Default ignore rules applied even when no .gitignore is present.
DEFAULT_IGNORE: list[str] = [
    ".git/",
    ".venv/",
    "venv/",
    "env/",
    ".env/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "node_modules/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".pytest_cache/",
    ".tox/",
    "dist/",
    "build/",
    "*.egg-info/",
    ".repox/",  # don't analyze our own output
    # legacy: python-venv-at-root pollution
    "Include/",
    "Lib/",
    "Scripts/",
    "pyvenv.cfg",
]


def language_for(ext: str) -> str | None:
    """Map a lowercased extension to a language name, or None if unknown."""
    return EXT_TO_LANG.get(ext.lower())


def is_binary_ext(ext: str) -> bool:
    """True if the extension is on the known-binary list."""
    return ext.lower() in BINARY_EXTS
