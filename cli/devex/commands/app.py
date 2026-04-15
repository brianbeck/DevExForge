"""Application management commands."""

from __future__ import annotations

import click

from devex.client import pass_client, DevExClient
from devex.output import print_error, print_success, print_table


@click.group("app")
def app() -> None:
    """Manage applications (register, deploy, inventory)."""


@app.command("register")
@click.option("--team", required=True, help="Team slug that owns the application.")
@click.option("--name", required=True, help="Application name (will be slugified).")
@click.option("--display-name", default=None, help="Human-readable display name. Defaults to --name.")
@click.option("--description", default=None, help="Application description.")
@click.option("--repo", "repo_url", default=None, help="Git repository URL.")
@click.option("--chart-path", default=None, help="Helm chart path within repo (e.g. deploy/helm).")
@click.option("--chart-repo", "chart_repo_url", default=None, help="Helm chart repo URL (if different from repo).")
@click.option("--owner", "owner_email", required=True, help="Owner email for notifications.")
@click.option(
    "--strategy",
    type=click.Choice(["rolling", "bluegreen", "canary"]),
    default="rolling",
    help="Default deployment strategy.",
)
@pass_client
def app_register(
    client: DevExClient,
    team: str,
    name: str,
    display_name: str | None,
    description: str | None,
    repo_url: str | None,
    chart_path: str | None,
    chart_repo_url: str | None,
    owner_email: str,
    strategy: str,
) -> None:
    """Register a new application."""
    payload: dict = {
        "name": name,
        "displayName": display_name or name,
        "ownerEmail": owner_email,
        "defaultStrategy": strategy,
    }
    if description:
        payload["description"] = description
    if repo_url:
        payload["repoUrl"] = repo_url
    if chart_path:
        payload["chartPath"] = chart_path
    if chart_repo_url:
        payload["chartRepoUrl"] = chart_repo_url
    result = client.post(f"/teams/{team}/applications", payload)
    print_success(f"Application '{result.get('name', name)}' registered for team '{team}'.")


@app.command("list")
@click.option("--team", default=None, help="Team slug. Omit with --all for global list (admin only).")
@click.option("--all", "list_all", is_flag=True, help="List all applications across all teams (admin only).")
@pass_client
def app_list(client: DevExClient, team: str | None, list_all: bool) -> None:
    """List applications."""
    if list_all:
        apps = client.get("/applications")
    elif team:
        apps = client.get(f"/teams/{team}/applications")
    else:
        print_error("Must specify --team <slug> or --all")
        return

    if isinstance(apps, dict):
        apps = apps.get("applications") or apps.get("items") or []
    if not apps:
        click.echo("No applications found.")
        return
    headers = ["Team", "Name", "Display Name", "Strategy", "Owner", "Deployments"]
    rows = [
        [
            a.get("slug", a.get("teamSlug", "-")),
            a.get("name", "-"),
            a.get("displayName", "-"),
            a.get("defaultStrategy", "rolling"),
            a.get("ownerEmail", "-"),
            str(len(a.get("deployments", []))),
        ]
        for a in apps
    ]
    print_table(headers, rows)


@app.command("get")
@click.argument("team")
@click.argument("name")
@pass_client
def app_get(client: DevExClient, team: str, name: str) -> None:
    """Get application details."""
    result = client.get(f"/teams/{team}/applications/{name}")
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()

    console.print(Panel.fit(
        f"[bold]{result.get('displayName', name)}[/bold]\n"
        f"[dim]{result.get('description') or 'No description'}[/dim]",
        title=f"Application: {result.get('name', name)}",
    ))

    meta = Table(show_header=False, box=None)
    meta.add_column(style="cyan")
    meta.add_column()
    meta.add_row("Team", team)
    meta.add_row("Owner", result.get("ownerEmail", "-"))
    meta.add_row("Strategy", result.get("defaultStrategy", "rolling"))
    meta.add_row("Repo", result.get("repoUrl") or "-")
    meta.add_row("Chart Path", result.get("chartPath") or "-")
    meta.add_row("Created", result.get("createdAt", "-"))
    console.print(meta)

    deployments = result.get("deployments", [])
    if deployments:
        console.print()
        dep_table = Table(title="Deployments")
        dep_table.add_column("Tier")
        dep_table.add_column("Image Tag")
        dep_table.add_column("Health")
        dep_table.add_column("Sync")
        dep_table.add_column("Deployed")
        for d in deployments:
            dep_table.add_row(
                d.get("environmentTier", "-"),
                d.get("imageTag") or "-",
                d.get("healthStatus") or "-",
                d.get("syncStatus") or "-",
                d.get("deployedAt", "-")[:19] if d.get("deployedAt") else "-",
            )
        console.print(dep_table)
    else:
        console.print("\n[dim]No deployments yet.[/dim]")


@app.command("delete")
@click.argument("team")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure? This will delete the application and all its deployments.")
@pass_client
def app_delete(client: DevExClient, team: str, name: str) -> None:
    """Delete an application and all its deployments."""
    client.delete(f"/teams/{team}/applications/{name}")
    print_success(f"Application '{name}' deleted.")


@app.command("deploy")
@click.argument("team")
@click.argument("name")
@click.option("--tier", type=click.Choice(["dev", "staging", "production"]), required=True)
@click.option("--image-tag", default=None, help="Image tag to deploy.")
@click.option("--chart-version", default=None, help="Chart version.")
@click.option(
    "--strategy",
    type=click.Choice(["rolling", "bluegreen", "canary"]),
    default=None,
    help="Override default strategy.",
)
@pass_client
def app_deploy(
    client: DevExClient,
    team: str,
    name: str,
    tier: str,
    image_tag: str | None,
    chart_version: str | None,
    strategy: str | None,
) -> None:
    """Deploy an application to a tier."""
    payload: dict = {"tier": tier}
    if image_tag:
        payload["imageTag"] = image_tag
    if chart_version:
        payload["chartVersion"] = chart_version
    if strategy:
        payload["strategy"] = strategy
    result = client.post(f"/teams/{team}/applications/{name}/deploy", payload)
    print_success(f"Deployment started: {result.get('message', 'ok')}")
    if result.get("argocdAppName"):
        click.echo(f"Argo CD Application: {result['argocdAppName']}")
    if result.get("namespaceName"):
        click.echo(f"Namespace: {result['namespaceName']}")


@app.command("history")
@click.argument("team")
@click.argument("name")
@click.option("--limit", default=20, type=int)
@pass_client
def app_history(client: DevExClient, team: str, name: str, limit: int) -> None:
    """Show deployment history for an application."""
    result = client.get(f"/teams/{team}/applications/{name}/history", limit=limit)
    events = result.get("events") if isinstance(result, dict) else result
    if not events:
        click.echo("No deployment events.")
        return
    headers = ["Occurred", "Event", "From", "To", "Actor"]
    rows = [
        [
            (e.get("occurredAt") or "-")[:19],
            e.get("eventType", "-"),
            e.get("fromVersion") or "-",
            e.get("toVersion") or "-",
            e.get("actor", "-"),
        ]
        for e in events
    ]
    print_table(headers, rows)


@app.command("inventory")
@click.option("--team", default=None, help="Team slug. Omit for global inventory (admin only).")
@pass_client
def app_inventory(client: DevExClient, team: str | None) -> None:
    """Show cross-environment inventory grid."""
    if team:
        data = client.get(f"/teams/{team}/applications/inventory")
    else:
        data = client.get("/applications/inventory")
    rows_data = data.get("rows") if isinstance(data, dict) else data
    if not rows_data:
        click.echo("No applications found.")
        return

    headers = ["Team", "Application", "Dev", "Staging", "Production"]
    table_rows = []
    for r in rows_data:
        depls = r.get("deployments", {})

        def cell(d: dict | None) -> str:
            if not d:
                return "-"
            tag = d.get("imageTag", "?")
            health = d.get("healthStatus", "?")
            return f"{tag} [{health}]"

        table_rows.append([
            r.get("teamSlug", "-"),
            r.get("displayName", r.get("name", "-")),
            cell(depls.get("dev")),
            cell(depls.get("staging")),
            cell(depls.get("production")),
        ])
    print_table(headers, table_rows)


@app.command("refresh")
@click.argument("team")
@click.argument("name")
@pass_client
def app_refresh(client: DevExClient, team: str, name: str) -> None:
    """Manually refresh application status from Argo CD."""
    client.post(f"/teams/{team}/applications/{name}/refresh", {})
    print_success(f"Refresh triggered for '{name}'.")
