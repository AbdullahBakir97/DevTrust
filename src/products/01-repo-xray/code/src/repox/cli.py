"""Repo X-ray command-line interface.

Built on Typer + Rich for clean, friendly terminal output. Three commands:

    repox build [PATH]   - analyze a repo and emit .repox/architecture.{json,md}
    repox version        - print version
    repox info  [PATH]   - quick stats without writing files (debugging aid)
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from repox import __version__
from repox.analyzer import analyze
from repox.output import write_json, write_markdown

app = typer.Typer(
    name="repox",
    help="Repo X-ray - codebase architecture model that AI tools and DevTrust products consume.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()


@app.command()
def version() -> None:
    """Print the installed Repo X-ray version."""
    console.print(f"repox [bold]v{__version__}[/bold]")


@app.command()
def build(
    path: Annotated[
        Path,
        typer.Argument(help="Repo to analyze. Defaults to current directory."),
    ] = Path("."),
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Suppress non-essential output.")
    ] = False,
) -> None:
    """Analyze a repo and write `.repox/architecture.{json,md}`."""
    if not path.exists():
        console.print(f"[red]Error:[/red] path does not exist: {path}")
        raise typer.Exit(code=2)
    if not path.is_dir():
        console.print(f"[red]Error:[/red] not a directory: {path}")
        raise typer.Exit(code=2)

    if not quiet:
        console.print(f"[bold]Analyzing[/bold] {path.resolve()}")

    arch = analyze(path)
    json_path = write_json(arch, path)
    md_path = write_markdown(arch, path)

    if quiet:
        return

    table = Table(title=f"\n{arch.repo.name}", title_style="bold", show_header=True)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="white", justify="right")
    table.add_row("Files", f"{arch.repo.total_files:,}")
    table.add_row("Lines", f"{arch.repo.total_lines:,}")
    table.add_row("Languages", str(len(arch.languages)))
    table.add_row("Entry points", str(len(arch.entry_points)))
    console.print(table)

    if arch.languages:
        lang_table = Table(title="Top languages", show_header=True, header_style="bold")
        lang_table.add_column("Language", style="cyan")
        lang_table.add_column("Files", justify="right")
        lang_table.add_column("Lines", justify="right", style="white")
        for lang in arch.languages[:8]:
            lang_table.add_row(lang.name, f"{lang.file_count:,}", f"{lang.line_count:,}")
        console.print(lang_table)

    console.print(f"\n[green]✓[/green] wrote [bold]{json_path}[/bold]")
    console.print(f"[green]✓[/green] wrote [bold]{md_path}[/bold]")


@app.command()
def info(
    path: Annotated[
        Path, typer.Argument(help="Repo to inspect. Defaults to current directory.")
    ] = Path("."),
) -> None:
    """Quick stats without writing files. Useful for debugging."""
    if not path.is_dir():
        console.print(f"[red]Error:[/red] not a directory: {path}")
        raise typer.Exit(code=2)

    arch = analyze(path)
    console.print(
        f"[bold]{arch.repo.name}[/bold]  ({arch.repo.total_files} files, "
        f"{arch.repo.total_lines:,} lines, {len(arch.languages)} languages)"
    )
    if arch.languages:
        top = arch.languages[0]
        console.print(
            f"Top language: [cyan]{top.name}[/cyan] "
            f"({top.file_count} files, {top.line_count:,} lines)"
        )
    if arch.entry_points:
        eps_str = ", ".join(f"[bold]{ep.path}[/bold]" for ep in arch.entry_points[:5])
        console.print("Entry points: " + eps_str)
