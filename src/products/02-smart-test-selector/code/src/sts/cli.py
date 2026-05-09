"""Smart Test Selector command-line interface.

Built on Typer + Rich. Three commands:

    sts select [--repo PATH]  - decide which tests to run for a change set
    sts version               - print version
    sts info   [--repo PATH]  - quick stats: how many tests by framework

When a `.repox/architecture.json` file exists at the repo root, sts uses
its file list automatically (faster, gitignore-aware). Disable with
`--no-use-repox` if you want sts to do its own walk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from sts import __version__
from sts.diff import (
    from_cli_args,
    from_git_auto,
    from_path_list_file,
    from_unified_diff,
)
from sts.frameworks import detect_all
from sts.output import write_json, write_markdown
from sts.repox_integration import architecture_path, load_files
from sts.selector import select as select_engine

app = typer.Typer(
    name="sts",
    help="Smart Test Selector - given a code change, decide which tests must run.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()


def _walk_repo(root: Path) -> list[str]:
    """Fallback file walker used when no `.repox/architecture.json` exists."""
    skip_dirs = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".repox",
        ".sts",
        "dist",
        "build",
    }
    paths: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        paths.append(rel.as_posix())
    return paths


# Keep the historical name exposed for tests that already imported it.
_list_repo_files = _walk_repo


def _resolve_repo_files(
    root: Path,
    use_repox: bool,
    quiet: bool,
) -> tuple[list[str], object | None]:
    """Pick the file source: repox artifact when allowed and present, else walk.

    Returns (paths, repox_artifact). The artifact is the typed RepoxArtifact
    when used; None otherwise.
    """
    if use_repox:
        artifact = load_files(root)
        if artifact is not None:
            if not quiet:
                console.print(
                    f"[dim]Using[/dim] [bold]{architecture_path(root).name}[/bold] "
                    f"[dim]({len(artifact.paths)} files, repox v{artifact.tool_version})[/dim]"
                )
            return artifact.paths, artifact
    return _walk_repo(root), None


def _resolve_changed(
    repo: Path,
    changed: list[str] | None,
    diff_path: Path | None,
    paths_file: Path | None,
) -> tuple[list[str], str]:
    """Pick the highest-priority change source. Returns (paths, source-label)."""
    if changed:
        return from_cli_args(changed, repo), "cli"
    if diff_path is not None:
        text = diff_path.read_text(encoding="utf-8", errors="ignore")
        return from_unified_diff(text, repo), "diff-file"
    if paths_file is not None:
        text = paths_file.read_text(encoding="utf-8", errors="ignore")
        return from_path_list_file(text, repo), "cli"
    auto = from_git_auto(repo)
    if auto is not None:
        return auto, "git-auto"
    return [], "cli"


@app.command()
def version() -> None:
    """Print the installed Smart Test Selector version."""
    console.print(f"sts [bold]v{__version__}[/bold]")


@app.command()
def select(
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repo to analyze. Defaults to current directory."),
    ] = Path("."),
    changed: Annotated[
        list[str] | None,
        typer.Option(
            "--changed",
            "-c",
            help="Path(s) that changed. Repeat for multiple files.",
        ),
    ] = None,
    diff_path: Annotated[
        Path | None,
        typer.Option("--diff", "-d", help="Path to a unified-diff file."),
    ] = None,
    paths_file: Annotated[
        Path | None,
        typer.Option("--from-file", "-f", help="Path to a text file of one path per line."),
    ] = None,
    use_repox: Annotated[
        bool,
        typer.Option(
            "--use-repox/--no-use-repox",
            help="Read .repox/architecture.json if present (default: yes).",
        ),
    ] = True,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress non-essential output."),
    ] = False,
) -> None:
    """Decide which tests must run, should run, or can skip."""
    if not repo.exists() or not repo.is_dir():
        console.print(f"[red]Error:[/red] not a directory: {repo}")
        raise typer.Exit(code=2)

    repo = repo.resolve()
    changed_files, source_label = _resolve_changed(repo, changed, diff_path, paths_file)

    if not quiet:
        console.print(f"[bold]Selecting tests for[/bold] {repo}")
        console.print(
            f"[dim]Change source:[/dim] {source_label}  "
            f"[dim]Changed files:[/dim] {len(changed_files)}"
        )

    repo_files, artifact = _resolve_repo_files(repo, use_repox, quiet)
    report = select_engine(
        repo,
        repo_files,
        changed_files,
        diff_source=source_label,
        repox_artifact=artifact,  # type: ignore[arg-type]
    )

    json_path = write_json(report, repo)
    md_path = write_markdown(report, repo)

    if quiet:
        return

    s = report.stats
    table = Table(title="\nSelection summary", show_header=True, header_style="bold")
    table.add_column("Priority", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("must-run", f"{s.must_run:,}")
    table.add_row("should-run", f"{s.should_run:,}")
    table.add_row("skip", f"{s.can_skip:,}")
    table.add_row("[bold]total tests[/bold]", f"[bold]{s.total_tests_in_repo:,}[/bold]")
    console.print(table)

    if report.fallback_run_all:
        console.print(f"[yellow]Fallback to run-all:[/yellow] {report.fallback_reason}")

    console.print(f"\n[green]✓[/green] wrote [bold]{json_path}[/bold]")
    console.print(f"[green]✓[/green] wrote [bold]{md_path}[/bold]")


@app.command()
def info(
    repo: Annotated[
        Path,
        typer.Option("--repo", "-r", help="Repo to inspect. Defaults to current directory."),
    ] = Path("."),
    use_repox: Annotated[
        bool,
        typer.Option(
            "--use-repox/--no-use-repox",
            help="Read .repox/architecture.json if present (default: yes).",
        ),
    ] = True,
) -> None:
    """Quick stats: how many tests in the repo, by framework. No files written."""
    if not repo.is_dir():
        console.print(f"[red]Error:[/red] not a directory: {repo}")
        raise typer.Exit(code=2)

    repo = repo.resolve()
    repo_files, _ = _resolve_repo_files(repo, use_repox, quiet=False)
    refs = detect_all(repo_files)

    by_fw: dict[str, int] = {}
    for r in refs:
        by_fw[r.framework] = by_fw.get(r.framework, 0) + 1

    console.print(f"[bold]{repo.name}[/bold]  ({len(repo_files)} files, {len(refs)} tests)")
    if by_fw:
        table = Table(title="Tests by framework", show_header=True, header_style="bold")
        table.add_column("Framework", style="cyan")
        table.add_column("Count", justify="right")
        for fw, count in sorted(by_fw.items(), key=lambda x: (-x[1], x[0])):
            table.add_row(fw, str(count))
        console.print(table)
