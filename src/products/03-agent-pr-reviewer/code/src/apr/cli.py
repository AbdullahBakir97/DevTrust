"""Agent-PR Reviewer command-line interface.

apr version
apr review [--repo PATH] [--changed FILE ...] [--title S] [--description S]
           [--diff PATH] [--enable-ai] [--ai-provider null|anthropic]
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from apr import __version__
from apr.engine import review as review_engine
from apr.llm import LLMProvider, build_provider
from apr.output import write_json, write_markdown

app = typer.Typer(
    name="apr",
    help="Agent-PR Reviewer - deterministic + AI-pattern review for PRs.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()


@app.command()
def version() -> None:
    """Print the installed Agent-PR Reviewer version."""
    console.print(f"apr [bold]v{__version__}[/bold]")


@app.command()
def review(
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repo to review. Defaults to current directory."),
    ] = Path("."),
    changed: Annotated[
        list[str] | None,
        typer.Option(
            "--changed",
            "-c",
            help="Path(s) that changed. Repeat for multiple files.",
        ),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option("--title", "-t", help="The PR title (for metadata checks)."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="The PR description / body."),
    ] = None,
    diff_path: Annotated[
        Path | None,
        typer.Option(
            "--diff",
            help=(
                "Path to a unified-diff file. Required for the "
                "ai-review:diff-comprehension rule when --enable-ai."
            ),
        ),
    ] = None,
    enable_ai: Annotated[
        bool,
        typer.Option(
            "--enable-ai/--no-enable-ai",
            help=(
                "Run the ai-review:* rule pack. Off by default. "
                "ai-review:hallucinated-symbol needs a "
                ".repox/architecture.json (run `repox build .` first)."
            ),
        ),
    ] = False,
    ai_provider: Annotated[
        str,
        typer.Option(
            "--ai-provider",
            help="LLM backend: 'null' (default, no calls) or 'anthropic'.",
        ),
    ] = "null",
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential output."),
    ] = False,
) -> None:
    """Run the review and emit `.apr/review.{json,md}`."""
    if not repo.exists() or not repo.is_dir():
        console.print(f"[red]Error:[/red] not a directory: {repo}")
        raise typer.Exit(code=2)

    repo = repo.resolve()
    files = list(changed or [])

    diff_text: str | None = None
    if diff_path is not None:
        try:
            diff_text = diff_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            console.print(f"[red]Error:[/red] cannot read diff: {exc}")
            raise typer.Exit(code=2) from exc

    provider: LLMProvider | None = None
    if enable_ai:
        # Anthropic API key from the conventional env var.
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        provider = build_provider(ai_provider, api_key)

    if not quiet:
        console.print(f"[bold]Reviewing[/bold] {repo}")
        console.print(f"[dim]Changed files:[/dim] {len(files)}")
        if enable_ai:
            console.print(f"[dim]AI rules:[/dim] enabled (provider: {ai_provider})")

    report = review_engine(
        repo,
        files,
        pr_title=title,
        pr_description=description,
        enable_ai=enable_ai,
        llm_provider=provider,
        diff=diff_text,
    )
    json_path = write_json(report, repo)
    md_path = write_markdown(report, repo)

    if quiet:
        return

    s = report.stats
    table = Table(title="\nReview summary", show_header=True, header_style="bold")
    table.add_column("Severity", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("info", str(s.info))
    table.add_row("warning", str(s.warning))
    table.add_row("error", str(s.error))
    table.add_row("critical", str(s.critical))
    table.add_row("[bold]total[/bold]", f"[bold]{s.total}[/bold]")
    console.print(table)
    if s.blocking > 0:
        console.print(f"[red]Blocking findings:[/red] {s.blocking} (error + critical)")
    console.print(f"\n[green]✓[/green] wrote [bold]{json_path}[/bold]")
    console.print(f"[green]✓[/green] wrote [bold]{md_path}[/bold]")
