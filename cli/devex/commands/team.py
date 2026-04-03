"""Team management commands."""

from __future__ import annotations

import click

from devex.client import pass_client, DevExClient
from devex.output import print_error, print_success, print_table, print_team


@click.group("team")
def team() -> None:
    """Manage teams."""


@team.command("create")
@click.option("--name", required=True, help="Team display name.")
@click.option("--description", default=None, help="Short description of the team.")
@click.option("--cost-center", default=None, help="Billing cost center code.")
@pass_client
def team_create(client: DevExClient, name: str, description: str | None, cost_center: str | None) -> None:
    """Create a new team."""
    payload: dict = {"displayName": name}
    if description is not None:
        payload["description"] = description
    if cost_center is not None:
        payload["costCenter"] = cost_center
    result = client.post("/teams", payload)
    print_success(f"Team '{result.get('displayName', name)}' created.")
    print_team(result)


@team.command("list")
@pass_client
def team_list(client: DevExClient) -> None:
    """List all teams."""
    data = client.get("/teams")
    teams = data.get("teams", []) if isinstance(data, dict) else data
    if not teams:
        click.echo("No teams found.")
        return
    rows = [
        [t.get("slug", "-"), t.get("displayName", "-"), t.get("description", "-") or "-", t.get("costCenter", "-") or "-"]
        for t in teams
    ]
    print_table(["Slug", "Name", "Description", "Cost Center"], rows)


@team.command("get")
@click.argument("slug")
@pass_client
def team_get(client: DevExClient, slug: str) -> None:
    """Show details for a team by its SLUG."""
    result = client.get(f"/teams/{slug}")
    print_team(result)


@team.command("delete")
@click.argument("slug")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@pass_client
def team_delete(client: DevExClient, slug: str, yes: bool) -> None:
    """Delete a team by its SLUG."""
    if not yes:
        click.confirm(f"Are you sure you want to delete team '{slug}'?", abort=True)
    client.delete(f"/teams/{slug}")
    print_success(f"Team '{slug}' deleted.")
