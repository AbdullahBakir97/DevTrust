"""WhyChanged command-line interface.

whychanged version
whychanged explain --repo PATH [--since 30m | --since-iso 2026-05-08T...]
                   [--service NAME] [--service-file FILE...]
                   [--github-repo owner/name] [--github-environment ENV]
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from whychanged import __version__
from whychanged.engine import explain as run_explain
from whychanged.output import write_json, write_markdown
from whychanged.providers import ChangeProvider, GitChangeProvider
from whychanged.providers_github import GitHubDeploymentsProvider

app = typer.Typer(
    name="whychanged",
    help="WhyChanged - production diff-detective for incident response.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

# `--since 30m` style window parsing. Accepts m/h/d suffixes; defaults
# to minutes when no unit is given.
_SINCE_RE = re.compile(r"^\s*(?P<n>\d+)\s*(?P<u>[mhd])?\s*$", re.IGNORECASE)


def _parse_window(text: str) -> timedelta:
    m = _SINCE_RE.match(text)
    if m is None:
        raise typer.BadParameter(
            f"--since {text!r} not understood; use forms like '30m', '2h', '1d'."
        )
    n = int(m.group("n"))
    unit = (m.group("u") or "m").lower()
    if unit == "m":
        return timedelta(minutes=n)
    if unit == "h":
        return timedelta(hours=n)
    return timedelta(days=n)


@app.command()
def version() -> None:
    """Print the installed WhyChanged version."""
    console.print(f"whychanged [bold]v{__version__}[/bold]")


@app.command()
def explain(
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repo root to read git history from."),
    ] = Path("."),
    since: Annotated[
        str,
        typer.Option(
            "--since",
            "-s",
            help="Window length: e.g. '30m', '2h', '1d'.",
        ),
    ] = "30m",
    incident_at: Annotated[
        str | None,
        typer.Option(
            "--incident-at",
            help=(
                "Incident start time in ISO-8601 (e.g. "
                "'2026-05-08T14:30:00+00:00'). Defaults to now."
            ),
        ),
    ] = None,
    service: Annotated[
        str | None,
        typer.Option("--service", help="Name of the service this report is about."),
    ] = None,
    service_files: Annotated[
        list[str] | None,
        typer.Option(
            "--service-file",
            help=(
                "Repo-relative file path that belongs to the affected service. "
                "Pass repeatedly. Changes touching any of these score higher."
            ),
        ),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Restrict git history to one branch (e.g. 'main')."),
    ] = None,
    github_repo: Annotated[
        str | None,
        typer.Option(
            "--github-repo",
            help=(
                "owner/repo to enable GitHub Deployments. Auth via "
                "WHYCHANGED_GITHUB_TOKEN or GITHUB_TOKEN env var."
            ),
        ),
    ] = None,
    github_environment: Annotated[
        str | None,
        typer.Option(
            "--github-environment",
            help="Filter GitHub Deployments to one environment.",
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential output."),
    ] = False,
) -> None:
    """Rank recent changes by likelihood of being the culprit."""
    if not repo.exists() or not repo.is_dir():
        console.print(f"[red]Error:[/red] not a directory: {repo}")
        raise typer.Exit(code=2)

    repo = repo.resolve()
    window = _parse_window(since)
    incident_dt: datetime | None = None
    if incident_at is not None:
        try:
            iso = incident_at.replace("Z", "+00:00")
            incident_dt = datetime.fromisoformat(iso)
        except ValueError as exc:
            raise typer.BadParameter(
                f"--incident-at {incident_at!r} is not ISO-8601: {exc}"
            ) from exc
    files_set = set(service_files or [])

    if not quiet:
        console.print(f"[bold]WhyChanged[/bold]  {repo}")
        console.print(f"[dim]Window:[/dim] {since}  [dim]Service:[/dim] {service or '(none)'}")

    providers: list[ChangeProvider] = [
        GitChangeProvider(repo_root=repo, branch=branch),
    ]
    if github_repo is not None:
        if "/" not in github_repo:
            console.print(
                f"[red]Error:[/red] --github-repo expects owner/repo, got {github_repo!r}"
            )
            raise typer.Exit(code=2)
        owner, name = github_repo.split("/", 1)
        providers.append(
            GitHubDeploymentsProvider(owner=owner, repo=name, environment=github_environment)
        )
        if not quiet:
            console.print(
                f"[dim]GitHub Deployments:[/dim] {github_repo}"
                + (f" (env={github_environment})" if github_environment else "")
            )

    report = run_explain(
        repo_root=repo,
        providers=providers,
        incident_at=incident_dt,
        service=service,
        service_files=files_set,
        window=window,
    )

    json_path = write_json(report, repo)
    md_path = write_markdown(report, repo)

    if quiet:
        return

    if not report.ranked:
        console.print("[yellow]No changes in window.[/yellow]")
        console.print(f"\n[green]✓[/green] wrote [bold]{json_path}[/bold]")
        console.print(f"[green]✓[/green] wrote [bold]{md_path}[/bold]")
        return

    table = Table(title="\nMost likely culprits", show_header=True, header_style="bold")
    table.add_column("Rank", justify="right", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("When", style="dim")
    table.add_column("Kind", style="cyan")
    table.add_column("Source", style="dim")
    table.add_column("Summary")
    for i, rc in enumerate(report.ranked[:10], start=1):
        table.add_row(
            str(i),
            f"{rc.score:.2f}",
            rc.change.timestamp.isoformat(timespec="seconds"),
            rc.change.kind,
            rc.change.source,
            rc.change.summary,
        )
    console.print(table)
    console.print(f"\n[green]✓[/green] wrote [bold]{json_path}[/bold]")
    console.print(f"[green]✓[/green] wrote [bold]{md_path}[/bold]")
