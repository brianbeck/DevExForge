"""Promotion request commands."""

from __future__ import annotations

import click

from devex.client import DevExClient, pass_client
from devex.output import console, print_success, print_table


@click.group("promote")
def promote() -> None:
    """Manage application promotion requests."""


@promote.command("request")
@click.argument("team_slug")
@click.argument("app_name")
@click.option("--to", "to_tier", required=True, type=click.Choice(["dev", "staging", "production"]))
@click.option("--image-tag", default=None, help="Image tag to promote.")
@click.option("--chart-version", default=None, help="Chart version to promote.")
@click.option(
    "--strategy",
    type=click.Choice(["rolling", "bluegreen", "canary"]),
    default=None,
    help="Deployment strategy override.",
)
@click.option("--notes", default=None, help="Notes for the promotion request.")
@pass_client
def promote_request(
    client: DevExClient,
    team_slug: str,
    app_name: str,
    to_tier: str,
    image_tag: str | None,
    chart_version: str | None,
    strategy: str | None,
    notes: str | None,
) -> None:
    """Create a promotion request."""
    payload: dict = {"toTier": to_tier}
    if image_tag:
        payload["imageTag"] = image_tag
    if chart_version:
        payload["chartVersion"] = chart_version
    if strategy:
        payload["strategy"] = strategy
    if notes:
        payload["notes"] = notes
    result = client.post(
        f"/teams/{team_slug}/applications/{app_name}/promotion-requests", payload
    )
    req_id = result.get("id", "?")
    status = result.get("status", "?")
    print_success(f"Promotion request {req_id} created (status: {status}).")


@promote.command("list")
@click.option("--team", default=None, help="Team slug to scope by.")
@click.option("--app", "app_name", default=None, help="Application name to filter by.")
@click.option("--status", "status_filter", default=None, help="Filter by status.")
@click.option("--tier", default=None, help="Filter by target tier.")
@pass_client
def promote_list(
    client: DevExClient,
    team: str | None,
    app_name: str | None,
    status_filter: str | None,
    tier: str | None,
) -> None:
    """List promotion requests."""
    params: dict = {}
    if status_filter:
        params["status"] = status_filter
    if tier:
        params["tier"] = tier
    if team and app_name:
        path = f"/teams/{team}/applications/{app_name}/promotion-requests"
    elif team:
        path = f"/teams/{team}/promotion-requests"
    else:
        path = "/promotion-requests"
    result = client.get(path, **params)
    items = result
    if isinstance(result, dict):
        items = result.get("items") or result.get("promotionRequests") or []
    if not items:
        click.echo("No promotion requests found.")
        return
    headers = ["ID", "App", "From->To", "Strategy", "Status", "Requested By", "Requested At"]
    rows = []
    for r in items:
        from_tier = r.get("fromTier") or "-"
        tgt_tier = r.get("toTier") or "-"
        rows.append([
            r.get("id", "-"),
            r.get("applicationName") or r.get("appName") or "-",
            f"{from_tier}->{tgt_tier}",
            r.get("strategy") or "-",
            r.get("status") or "-",
            r.get("requestedBy") or "-",
            (r.get("requestedAt") or "-")[:19],
        ])
    print_table(headers, rows)


@promote.command("get")
@click.argument("request_id")
@pass_client
def promote_get(client: DevExClient, request_id: str) -> None:
    """Show promotion request details and gate results."""
    result = client.get(f"/promotion-requests/{request_id}")
    from rich.panel import Panel
    from rich.table import Table

    from_tier = result.get("fromTier") or "-"
    to_tier = result.get("toTier") or "-"
    console.print(Panel.fit(
        f"[bold]{result.get('applicationName', '-')}[/bold]  "
        f"{from_tier} -> {to_tier}\n"
        f"Status: [bold]{result.get('status', '-')}[/bold]",
        title=f"Promotion Request {result.get('id', request_id)}",
    ))

    meta = Table(show_header=False, box=None)
    meta.add_column(style="cyan")
    meta.add_column()
    meta.add_row("Team", result.get("teamSlug", "-"))
    meta.add_row("Strategy", result.get("strategy", "-"))
    meta.add_row("Image Tag", result.get("imageTag") or "-")
    meta.add_row("Chart Version", result.get("chartVersion") or "-")
    meta.add_row("Requested By", result.get("requestedBy", "-"))
    meta.add_row("Requested At", result.get("requestedAt", "-"))
    meta.add_row("Notes", result.get("notes") or "-")
    console.print(meta)

    gates = result.get("gateResults") or result.get("gates") or []
    if gates:
        console.print()
        gt = Table(title="Gate Results")
        gt.add_column("Gate")
        gt.add_column("Type")
        gt.add_column("Enforcement")
        gt.add_column("Status")
        gt.add_column("Message")
        for g in gates:
            gt.add_row(
                str(g.get("name") or g.get("gateId") or "-"),
                g.get("gateType") or g.get("type") or "-",
                g.get("enforcement") or "-",
                g.get("status") or "-",
                g.get("message") or "-",
            )
        console.print(gt)
    else:
        console.print("\n[dim]No gate results.[/dim]")


@promote.command("approve")
@click.argument("request_id")
@click.option("--notes", default=None, help="Approval notes.")
@pass_client
def promote_approve(client: DevExClient, request_id: str, notes: str | None) -> None:
    """Approve a promotion request."""
    payload: dict = {}
    if notes:
        payload["notes"] = notes
    client.post(f"/promotion-requests/{request_id}/approve", payload)
    print_success(f"Promotion request {request_id} approved.")


@promote.command("reject")
@click.argument("request_id")
@click.option("--reason", required=True, help="Reason for rejection.")
@pass_client
def promote_reject(client: DevExClient, request_id: str, reason: str) -> None:
    """Reject a promotion request."""
    client.post(f"/promotion-requests/{request_id}/reject", {"reason": reason})
    print_success(f"Promotion request {request_id} rejected.")


@promote.command("force")
@click.argument("request_id")
@click.option("--reason", required=True, help="Justification for force-approval.")
@pass_client
def promote_force(client: DevExClient, request_id: str, reason: str) -> None:
    """Force-approve a promotion request, bypassing gates (admin only)."""
    console.print(
        "[bold yellow]WARNING:[/bold yellow] Force-approval bypasses blocking gates. "
        "This action is audited and reserved for platform administrators."
    )
    click.confirm("Continue?", abort=True)
    client.post(f"/promotion-requests/{request_id}/force", {"reason": reason})
    print_success(f"Promotion request {request_id} force-approved.")


@promote.command("rollback")
@click.argument("request_id")
@click.option("--reason", required=True, help="Reason for rollback.")
@pass_client
def promote_rollback(client: DevExClient, request_id: str, reason: str) -> None:
    """Roll back a completed promotion."""
    client.post(f"/promotion-requests/{request_id}/rollback", {"reason": reason})
    print_success(f"Promotion request {request_id} rolled back.")


@promote.command("cancel")
@click.argument("request_id")
@pass_client
def promote_cancel(client: DevExClient, request_id: str) -> None:
    """Cancel a pending promotion request."""
    client.post(f"/promotion-requests/{request_id}/cancel", {})
    print_success(f"Promotion request {request_id} cancelled.")
