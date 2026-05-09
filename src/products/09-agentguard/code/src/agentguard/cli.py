"""AgentGuard command-line interface.

agentguard version
agentguard policies              # list bundled baseline policies
agentguard check --tool stripe.charge --policy baseline-starter
                                 # dry-run a single tool call against a policy
"""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from agentguard import __version__
from agentguard.baseline import (
    baseline_starter_policy,
    deny_credential_disclosure,
    deny_destructive_filesystem,
    deny_money_movement,
)
from agentguard.engine import evaluate
from agentguard.models import Policy, ToolCall

app = typer.Typer(
    name="agentguard",
    help="AgentGuard - policy-as-code runtime for AI agents.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

_BASELINES: dict[str, Policy] = {
    "money-movement": deny_money_movement(),
    "destructive-filesystem": deny_destructive_filesystem(),
    "credential-disclosure": deny_credential_disclosure(),
    "baseline-starter": baseline_starter_policy(),
}


@app.command()
def version() -> None:
    """Print the installed AgentGuard version."""
    console.print(f"agentguard [bold]v{__version__}[/bold]")


@app.command()
def policies() -> None:
    """List the bundled baseline policies and their rule counts."""
    table = Table(title="Bundled baseline policies", show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Rules", justify="right")
    table.add_column("Description", style="dim")
    for name, policy in _BASELINES.items():
        table.add_row(name, str(len(policy.rules)), policy.description)
    console.print(table)


@app.command()
def check(
    tool: Annotated[
        str,
        typer.Option("--tool", "-t", help="Tool name being attempted (e.g. stripe.charge)."),
    ],
    policy: Annotated[
        str,
        typer.Option(
            "--policy",
            "-p",
            help=(
                "Bundled baseline policy name. One of: "
                "money-movement, destructive-filesystem, "
                "credential-disclosure, baseline-starter."
            ),
        ),
    ] = "baseline-starter",
    arguments_json: Annotated[
        str | None,
        typer.Option(
            "--arguments-json",
            "-a",
            help="JSON object of call arguments (e.g. '{\"recursive\":true}').",
        ),
    ] = None,
    agent: Annotated[
        str | None,
        typer.Option("--agent", help="Agent identifier to attribute the call to."),
    ] = None,
) -> None:
    """Dry-run a single tool call against a baseline policy."""
    chosen = _BASELINES.get(policy)
    if chosen is None:
        console.print(
            f"[red]Error:[/red] unknown policy {policy!r}. Try one of: {', '.join(_BASELINES)}"
        )
        raise typer.Exit(code=2)

    args: dict[str, object] = {}
    if arguments_json is not None:
        try:
            parsed = json.loads(arguments_json)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"--arguments-json is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise typer.BadParameter("--arguments-json must be a JSON object.")
        args = parsed

    call = ToolCall(tool=tool, arguments=args, agent=agent)
    decision = evaluate(chosen, call)

    color = {"allow": "green", "deny": "red", "require_approval": "yellow"}[decision.status]
    console.print(
        f"[bold]{decision.status.upper()}[/bold] "
        f"[{color}]({decision.matched_rule or 'default-deny'})[/{color}]"
    )
    console.print(f"[dim]reason:[/dim] {decision.reason}")
    if decision.tags:
        console.print(f"[dim]tags:[/dim] {', '.join(decision.tags)}")


def main() -> None:
    """Entry point for the `agentguard` console script."""
    app()


if __name__ == "__main__":
    main()
