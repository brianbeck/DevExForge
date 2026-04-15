"""Promotion gate administration commands."""

from __future__ import annotations

import json

import click

from devex.client import DevExClient, pass_client
from devex.output import print_error, print_success, print_table


@click.group("gates")
def gates() -> None:
    """Manage promotion gates (platform admins)."""


@gates.command("list")
@click.option(
    "--scope",
    type=click.Choice(["platform", "team"]),
    default=None,
    help="Filter by gate scope.",
)
@click.option("--tier", default=None, help="Filter by tier.")
@pass_client
def gates_list(client: DevExClient, scope: str | None, tier: str | None) -> None:
    """List promotion gates."""
    params: dict = {}
    if scope:
        params["scope"] = scope
    if tier:
        params["tier"] = tier
    result = client.get("/admin/promotion-gates", **params)
    items = result
    if isinstance(result, dict):
        items = result.get("items") or result.get("gates") or []
    if not items:
        click.echo("No promotion gates found.")
        return

    headers = ["ID", "Scope", "Tier", "Gate Type", "Enforcement", "Config", "Created By"]
    rows = []
    for g in items:
        cfg = g.get("config") or {}
        cfg_str = json.dumps(cfg, separators=(",", ":")) if cfg else "{}"
        if len(cfg_str) > 40:
            cfg_str = cfg_str[:37] + "..."
        rows.append([
            g.get("id", "-"),
            g.get("scope", "-"),
            g.get("tier", "-"),
            g.get("gateType") or g.get("type") or "-",
            g.get("enforcement", "-"),
            cfg_str,
            g.get("createdBy", "-"),
        ])
    print_table(headers, rows)


@gates.command("add")
@click.option("--tier", required=True, type=click.Choice(["dev", "staging", "production"]))
@click.option("--type", "gate_type", required=True, help="Gate type identifier.")
@click.option(
    "--enforcement",
    type=click.Choice(["blocking", "advisory"]),
    default="blocking",
    show_default=True,
)
@click.option("--config", "config_json", default=None, help="Gate configuration as JSON string.")
@pass_client
def gates_add(
    client: DevExClient,
    tier: str,
    gate_type: str,
    enforcement: str,
    config_json: str | None,
) -> None:
    """Add a platform-scoped promotion gate."""
    if config_json:
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as exc:
            print_error(f"Invalid --config JSON: {exc}")
            raise click.Abort()
    else:
        config = {}
    payload = {
        "scope": "platform",
        "tier": tier,
        "gateType": gate_type,
        "enforcement": enforcement,
        "config": config,
    }
    result = client.post("/admin/promotion-gates", payload)
    gate_id = result.get("id", "?") if isinstance(result, dict) else "?"
    print_success(f"Promotion gate {gate_id} created ({gate_type} on {tier}).")


@gates.command("remove")
@click.argument("gate_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@pass_client
def gates_remove(client: DevExClient, gate_id: str, yes: bool) -> None:
    """Remove a promotion gate."""
    if not yes:
        click.confirm(f"Delete promotion gate {gate_id}?", abort=True)
    client.delete(f"/admin/promotion-gates/{gate_id}")
    print_success(f"Promotion gate {gate_id} removed.")
