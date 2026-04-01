"""Environment management commands."""

from __future__ import annotations

import click

from devex.client import pass_client, DevExClient
from devex.output import print_environment, print_error, print_success, print_table


@click.group("env")
def env() -> None:
    """Manage team environments."""


@env.command("create")
@click.argument("slug")
@click.option(
    "--tier",
    required=True,
    type=click.Choice(["dev", "staging", "production"]),
    help="Environment tier.",
)
@click.option("--cpu-request", default=None, help="CPU request quota (e.g. '500m', '2').")
@click.option("--memory-request", default=None, help="Memory request quota (e.g. '512Mi', '2Gi').")
@click.option("--pods", default=None, type=int, help="Maximum number of pods.")
@pass_client
def env_create(
    client: DevExClient,
    slug: str,
    tier: str,
    cpu_request: str | None,
    memory_request: str | None,
    pods: int | None,
) -> None:
    """Create an environment for team SLUG."""
    payload: dict = {"tier": tier}
    quota: dict = {}
    if cpu_request is not None:
        quota["cpu_request"] = cpu_request
    if memory_request is not None:
        quota["memory_request"] = memory_request
    if pods is not None:
        quota["pods"] = pods
    if quota:
        payload["quota"] = quota

    result = client.post(f"/teams/{slug}/environments", payload)
    print_success(f"Environment '{tier}' created for team '{slug}'.")
    print_environment(result)


@env.command("list")
@click.argument("slug")
@pass_client
def env_list(client: DevExClient, slug: str) -> None:
    """List environments for team SLUG."""
    envs = client.get(f"/teams/{slug}/environments")
    if not envs:
        print_error(f"No environments found for team '{slug}'.")
        return
    rows = [
        [
            e.get("tier", "-"),
            e.get("namespace", "-"),
            e.get("phase", "-"),
            e.get("created_at", "-"),
        ]
        for e in envs
    ]
    print_table(["Tier", "Namespace", "Phase", "Created"], rows)


@env.command("get")
@click.argument("slug")
@click.argument("tier", type=click.Choice(["dev", "staging", "production"]))
@pass_client
def env_get(client: DevExClient, slug: str, tier: str) -> None:
    """Show details for an environment of team SLUG at TIER."""
    result = client.get(f"/teams/{slug}/environments/{tier}")
    print_environment(result)


@env.command("delete")
@click.argument("slug")
@click.argument("tier", type=click.Choice(["dev", "staging", "production"]))
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@pass_client
def env_delete(client: DevExClient, slug: str, tier: str, yes: bool) -> None:
    """Delete the TIER environment for team SLUG."""
    if not yes:
        click.confirm(
            f"Are you sure you want to delete the '{tier}' environment for team '{slug}'?",
            abort=True,
        )
    client.delete(f"/teams/{slug}/environments/{tier}")
    print_success(f"Environment '{tier}' deleted for team '{slug}'.")


@env.command("status")
@click.argument("slug")
@click.argument("tier", type=click.Choice(["dev", "staging", "production"]))
@pass_client
def env_status(client: DevExClient, slug: str, tier: str) -> None:
    """Show reconciliation status of the TIER environment for team SLUG."""
    result = client.get(f"/teams/{slug}/environments/{tier}/status")
    status = result if isinstance(result, dict) else {}

    state = status.get("state", "unknown")
    style = {"synced": "bold green", "progressing": "bold yellow", "error": "bold red"}.get(
        state, "bold white"
    )

    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    lines = [
        f"[bold]Team:[/bold]        {slug}",
        f"[bold]Tier:[/bold]        {tier}",
        f"[bold]State:[/bold]       [{style}]{state}[/{style}]",
        f"[bold]Message:[/bold]     {status.get('message', '-')}",
        f"[bold]Last Synced:[/bold] {status.get('last_synced', '-')}",
    ]
    conditions = status.get("conditions")
    if conditions:
        lines.append("")
        lines.append("[bold underline]Conditions[/bold underline]")
        for cond in conditions:
            ctype = cond.get("type", "?")
            cstatus = cond.get("status", "?")
            cmsg = cond.get("message", "")
            lines.append(f"  {ctype}: {cstatus}  {cmsg}")

    console.print(
        Panel("\n".join(lines), title=f"Status: {slug}/{tier}", border_style="cyan")
    )
