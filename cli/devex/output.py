"""Output formatting helpers using rich."""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()
error_console = Console(stderr=True)


def print_table(headers: list[str], rows: list[list[Any]]) -> None:
    """Print a formatted table with headers and rows."""
    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*[str(cell) if cell is not None else "-" for cell in row])
    console.print(table)


def print_team(team: dict[str, Any]) -> None:
    """Print detailed team information in a panel."""
    lines = [
        f"[bold]Name:[/bold]        {team.get('name', '-')}",
        f"[bold]Slug:[/bold]        {team.get('slug', '-')}",
        f"[bold]Description:[/bold] {team.get('description', '-')}",
        f"[bold]Cost Center:[/bold] {team.get('cost_center', '-')}",
        f"[bold]Created:[/bold]     {team.get('created_at', '-')}",
        f"[bold]Updated:[/bold]     {team.get('updated_at', '-')}",
    ]
    members = team.get("members")
    if members is not None:
        lines.append(f"[bold]Members:[/bold]     {len(members)}")
    environments = team.get("environments")
    if environments is not None:
        lines.append(f"[bold]Environments:[/bold] {len(environments)}")
    console.print(
        Panel("\n".join(lines), title=f"Team: {team.get('name', '?')}", border_style="blue")
    )


def print_environment(env: dict[str, Any]) -> None:
    """Print detailed environment information in a panel."""
    lines = [
        f"[bold]Team:[/bold]       {env.get('team_slug', '-')}",
        f"[bold]Tier:[/bold]       {env.get('tier', '-')}",
        f"[bold]Namespace:[/bold]  {env.get('namespace', '-')}",
        f"[bold]Phase:[/bold]      {env.get('phase', '-')}",
        f"[bold]Created:[/bold]    {env.get('created_at', '-')}",
    ]
    quota = env.get("quota")
    if quota:
        lines.append("")
        lines.append("[bold underline]Resource Quota[/bold underline]")
        lines.append(f"  CPU Request:    {quota.get('cpu_request', '-')}")
        lines.append(f"  Memory Request: {quota.get('memory_request', '-')}")
        lines.append(f"  Pods:           {quota.get('pods', '-')}")
    status = env.get("status")
    if status:
        lines.append("")
        lines.append("[bold underline]Reconciliation Status[/bold underline]")
        lines.append(f"  State:          {status.get('state', '-')}")
        lines.append(f"  Message:        {status.get('message', '-')}")
        lines.append(f"  Last Synced:    {status.get('last_synced', '-')}")
    tier = env.get("tier", "?")
    team = env.get("team_slug", "?")
    console.print(
        Panel("\n".join(lines), title=f"Environment: {team}/{tier}", border_style="green")
    )


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(Text(f"Error: {message}", style="bold red"))


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(Text(message, style="bold green"))
