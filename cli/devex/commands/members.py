"""Team member management commands."""

from __future__ import annotations

import click

from devex.client import pass_client, DevExClient
from devex.output import print_error, print_success, print_table


@click.group("members")
def members() -> None:
    """Manage team members."""


@members.command("add")
@click.argument("slug")
@click.option("--email", required=True, help="Member email address.")
@click.option("--role", required=True, type=click.Choice(["owner", "admin", "member", "viewer"]), help="Role to assign.")
@pass_client
def members_add(client: DevExClient, slug: str, email: str, role: str) -> None:
    """Add a member to team SLUG."""
    result = client.post(f"/teams/{slug}/members", {"email": email, "role": role})
    print_success(f"Added {email} to team '{slug}' with role '{role}'.")


@members.command("list")
@click.argument("slug")
@pass_client
def members_list(client: DevExClient, slug: str) -> None:
    """List members of team SLUG."""
    members_data = client.get(f"/teams/{slug}/members")
    if not members_data:
        print_error(f"No members found for team '{slug}'.")
        return
    rows = [
        [m.get("email", "-"), m.get("role", "-"), m.get("added_at", "-")]
        for m in members_data
    ]
    print_table(["Email", "Role", "Added"], rows)


@members.command("update")
@click.argument("slug")
@click.argument("email")
@click.option("--role", required=True, type=click.Choice(["owner", "admin", "member", "viewer"]), help="New role.")
@pass_client
def members_update(client: DevExClient, slug: str, email: str, role: str) -> None:
    """Update the role of EMAIL in team SLUG."""
    client.patch(f"/teams/{slug}/members/{email}", {"role": role})
    print_success(f"Updated {email} role to '{role}' in team '{slug}'.")


@members.command("remove")
@click.argument("slug")
@click.argument("email")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@pass_client
def members_remove(client: DevExClient, slug: str, email: str, yes: bool) -> None:
    """Remove EMAIL from team SLUG."""
    if not yes:
        click.confirm(f"Remove {email} from team '{slug}'?", abort=True)
    client.delete(f"/teams/{slug}/members/{email}")
    print_success(f"Removed {email} from team '{slug}'.")
