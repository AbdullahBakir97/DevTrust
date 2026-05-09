"""Agent Trace SDK command-line interface.

agtrace version
agtrace dump --from-file traces.jsonl   # pretty-print one trace tree
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.tree import Tree

from agtrace import __version__
from agtrace.models import Span

app = typer.Typer(
    name="agtrace",
    help="Agent Trace SDK - agent-aware tracing.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _load_spans(path: Path) -> Iterable[Span]:
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                yield Span.model_validate(data)
            except Exception:
                continue


def _build_tree(spans: list[Span], root: Span) -> Tree:
    """Build a Rich Tree rooted at `root`, walking children via parent_span_id."""
    by_parent: dict[str | None, list[Span]] = {}
    for s in spans:
        by_parent.setdefault(s.parent_span_id, []).append(s)

    def _label(span: Span) -> str:
        duration = (
            (span.end_time - span.start_time).total_seconds() if span.end_time is not None else None
        )
        dur_text = f" ({duration * 1000:.0f}ms)" if duration is not None else ""
        status_text = "" if span.status == "ok" else f" [red]{span.status}[/red]"
        return f"[bold]{span.name}[/bold] [dim]({span.kind})[/dim]{dur_text}{status_text}"

    def _add(node: Tree, span: Span) -> None:
        sub = node.add(_label(span))
        for attr_k, attr_v in span.attributes.items():
            sub.add(f"[dim]{attr_k}=[/dim]{attr_v}")
        for child in by_parent.get(span.span_id, []):
            _add(sub, child)

    tree = Tree(_label(root))
    for attr_k, attr_v in root.attributes.items():
        tree.add(f"[dim]{attr_k}=[/dim]{attr_v}")
    for child in by_parent.get(root.span_id, []):
        _add(tree, child)
    return tree


@app.command()
def version() -> None:
    """Print the installed Agent Trace version."""
    console.print(f"agtrace [bold]v{__version__}[/bold]")


@app.command()
def dump(
    from_file: Annotated[
        Path,
        typer.Option(
            "--from-file",
            "-f",
            help="JSONL file of spans to render.",
        ),
    ] = Path(".agtrace/traces.jsonl"),
    trace_id: Annotated[
        str | None,
        typer.Option(
            "--trace",
            help="Render only spans matching this trace_id (default: most recent).",
        ),
    ] = None,
) -> None:
    """Pretty-print a trace tree to the terminal."""
    spans = list(_load_spans(from_file))
    if not spans:
        console.print("[yellow]No spans in input.[/yellow]")
        return

    if trace_id is None:
        # Most recent trace = the trace_id of the newest span by end_time.
        latest = max(spans, key=lambda s: s.end_time or s.start_time)
        trace_id = latest.trace_id

    selected = [s for s in spans if s.trace_id == trace_id]
    if not selected:
        console.print(f"[yellow]No spans for trace_id {trace_id!r}.[/yellow]")
        return

    root = next(
        (s for s in selected if s.parent_span_id is None),
        selected[0],
    )
    console.print(f"\n[bold]trace_id:[/bold] {trace_id}")
    console.print(f"[dim]spans:[/dim] {len(selected)}")
    console.print(_build_tree(selected, root))
