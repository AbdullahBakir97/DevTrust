"""JSONL-backed store for TokenUsage events.

One row per call, one file per day (or whatever rotation the operator
prefers). The format is line-delimited JSON so files can be tailed,
shipped, and grep-ed without a parser. Each line is a single
`TokenUsage.model_dump_json()`.

For v0.0.1 we don't ship a database backend; operators with high
volume should rotate files daily and aggregate offline via
`tokencost report --from-file <day>.jsonl`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Iterator
from pathlib import Path

from tokencost.models import TokenUsage

logger = logging.getLogger(__name__)


def append(path: Path, usage: TokenUsage) -> None:
    """Append one TokenUsage row as a single JSON line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(usage.model_dump_json(exclude_none=False))
        f.write("\n")


def append_many(path: Path, rows: Iterable[TokenUsage]) -> int:
    """Append multiple rows. Returns the count actually written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(row.model_dump_json(exclude_none=False))
            f.write("\n")
            written += 1
    return written


def load(path: Path) -> Iterator[TokenUsage]:
    """Yield TokenUsage rows from a JSONL file, skipping malformed lines."""
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("%s:%d: bad JSON, skipping (%s)", path, lineno, exc)
                continue
            try:
                yield TokenUsage.model_validate(data)
            except Exception as exc:
                logger.warning("%s:%d: row failed validation, skipping (%s)", path, lineno, exc)
                continue


def load_many(paths: Iterable[Path]) -> Iterator[TokenUsage]:
    """Stream rows from multiple JSONL files."""
    for path in paths:
        yield from load(path)
