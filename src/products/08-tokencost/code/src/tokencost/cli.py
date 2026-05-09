"""TokenCost command-line interface.

    tokencost version
    tokencost record --provider anthropic --model claude-sonnet-4-6 \
        --input-tokens 1234 --output-tokens 567 --feature pr-review
    tokencost report --from-file .tokencost/usage.jsonl
    tokencost prices
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tokencost import __version__
from tokencost.aggregate import aggregate
from tokencost.models import MICROS_PER_USD, TokenUsage
from tokencost.output import write_json, write_markdown
from tokencost.prices import estimate_cost_micros, known_models
from tokencost.store import append, load_many

app = typer.Typer(
    name="tokencost",
    help="TokenCost - financial-grade LLM spend attribution.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _fmt_usd(micros: int) -> str:
    usd = micros / MICROS_PER_USD
    if abs(usd) >= 0.01 or usd == 0:
        return f"${usd:,.2f}"
    return f"${usd:,.4f}"


@app.command()
def version() -> None:
    """Print the installed TokenCost version."""
    console.print(f"tokencost [bold]v{__version__}[/bold]")


@app.command()
def prices() -> None:
    """List the per-model price table baked into this build."""
    table = Table(
        title="\nKnown model prices (micro-USD per 1M tokens)",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Provider", style="cyan")
    table.add_column("Model")
    table.add_column("Input $/1M", justify="right")
    table.add_column("Output $/1M", justify="right")
    for p in known_models():
        table.add_row(
            p.provider,
            p.model,
            _fmt_usd(p.input_micros_per_mtok),
            _fmt_usd(p.output_micros_per_mtok),
        )
    console.print(table)


@app.command()
def record(
    provider: Annotated[str, typer.Option("--provider", "-p")],
    model: Annotated[str, typer.Option("--model", "-m")],
    input_tokens: Annotated[int, typer.Option("--input-tokens", min=0)],
    output_tokens: Annotated[int, typer.Option("--output-tokens", min=0)],
    feature: Annotated[str | None, typer.Option("--feature")] = None,
    environment: Annotated[str | None, typer.Option("--environment", "--env")] = None,
    actor: Annotated[str | None, typer.Option("--actor")] = None,
    request_id: Annotated[str | None, typer.Option("--request-id")] = None,
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            "-o",
            help="JSONL file to append to (default: .tokencost/usage.jsonl).",
        ),
    ] = Path(".tokencost/usage.jsonl"),
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential output."),
    ] = False,
) -> None:
    """Append one usage event to the JSONL log."""
    cost = estimate_cost_micros(provider, model, input_tokens, output_tokens)
    if cost is None:
        console.print(
            f"[yellow]Warning:[/yellow] no price for {provider}/{model}; "
            "recording with cost=0. Use `tokencost prices` to see known models."
        )
        cost = 0
    usage = TokenUsage(
        timestamp=datetime.now(UTC),
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_micros=cost,
        feature=feature,
        environment=environment,
        actor=actor,
        request_id=request_id,
    )
    append(out, usage)
    if not quiet:
        console.print(
            f"[green]✓[/green] recorded "
            f"{input_tokens + output_tokens:,} tokens "
            f"({_fmt_usd(cost)}) -> {out}"
        )


@app.command()
def report(
    from_file: Annotated[
        list[Path] | None,
        typer.Option(
            "--from-file",
            "-f",
            help="JSONL file(s) to read. Repeat for multiple files.",
        ),
    ] = None,
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            "-o",
            help="Directory the report is written under (default: cwd).",
        ),
    ] = Path("."),
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential output."),
    ] = False,
) -> None:
    """Aggregate usage rows into a CostReport JSON + Markdown."""
    paths = list(from_file or [Path(".tokencost/usage.jsonl")])
    cost_report = aggregate(load_many(paths))

    json_path = write_json(cost_report, out)
    md_path = write_markdown(cost_report, out)

    if quiet:
        return

    if cost_report.total_calls == 0:
        console.print("[yellow]No usage rows found in input.[/yellow]")
        console.print(f"\n[green]✓[/green] wrote [bold]{json_path}[/bold]")
        console.print(f"[green]✓[/green] wrote [bold]{md_path}[/bold]")
        return

    table = Table(title="\nLLM cost summary", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Total cost", _fmt_usd(cost_report.total_cost_micros))
    table.add_row("Total calls", f"{cost_report.total_calls:,}")
    table.add_row("Input tokens", f"{cost_report.total_input_tokens:,}")
    table.add_row("Output tokens", f"{cost_report.total_output_tokens:,}")
    console.print(table)

    if cost_report.by_feature:
        feat_table = Table(title="By feature", show_header=True, header_style="bold")
        feat_table.add_column("Feature", style="cyan")
        feat_table.add_column("Calls", justify="right")
        feat_table.add_column("Cost", justify="right")
        for b in cost_report.by_feature[:10]:
            feat_table.add_row(b.label, f"{b.calls:,}", _fmt_usd(b.cost_micros))
        console.print(feat_table)

    console.print(f"\n[green]✓[/green] wrote [bold]{json_path}[/bold]")
    console.print(f"[green]✓[/green] wrote [bold]{md_path}[/bold]")
