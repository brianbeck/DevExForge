"""Argo Rollouts commands."""

from __future__ import annotations

import sys

import click
import httpx

from devex.client import DevExClient, pass_client
from devex.output import console, print_error, print_success

_PHASE_COLORS = {
    "Healthy": "green",
    "Progressing": "cyan",
    "Paused": "yellow",
    "Degraded": "red",
    "Aborted": "red",
}


def _handle_rollouts_missing(response: httpx.Response) -> bool:
    """Return True if the response indicates Argo Rollouts is not installed."""
    if response.status_code == 503:
        print_error("Argo Rollouts is not installed on the target cluster.")
        return True
    return False


def _rollout_request(client: DevExClient, method: str, path: str, tier: str) -> dict | None:
    """Issue a rollout request, handling 503 without exiting."""
    try:
        response = client._client.request(method, path, params={"tier": tier})
    except httpx.ConnectError:
        print_error(f"Could not connect to the API at {client.base_url}")
        sys.exit(1)
    except httpx.HTTPError as exc:
        print_error(f"HTTP error: {exc}")
        sys.exit(1)

    if _handle_rollouts_missing(response):
        sys.exit(2)

    try:
        body = response.json()
    except Exception:
        body = None

    if response.is_success:
        return body if isinstance(body, dict) else {}

    detail = ""
    if isinstance(body, dict):
        detail = body.get("detail") or body.get("message") or ""
    if not detail:
        detail = response.text or f"HTTP {response.status_code}"
    print_error(f"[{response.status_code}] {detail}")
    sys.exit(1)


@click.group("rollout")
def rollout() -> None:
    """Manage Argo Rollouts for applications."""


@rollout.command("status")
@click.argument("team_slug")
@click.argument("app_name")
@click.option(
    "--tier",
    type=click.Choice(["dev", "staging", "production"]),
    default="production",
    show_default=True,
)
@pass_client
def rollout_status(client: DevExClient, team_slug: str, app_name: str, tier: str) -> None:
    """Show rollout status."""
    result = _rollout_request(
        client, "GET", f"/teams/{team_slug}/applications/{app_name}/rollout", tier
    ) or {}

    from rich.panel import Panel
    from rich.table import Table

    strategy = result.get("strategy", "-")
    phase = result.get("phase") or result.get("status") or "-"
    phase_color = _PHASE_COLORS.get(phase, "white")

    console.print(Panel.fit(
        f"[bold]{app_name}[/bold] ({team_slug}) -- tier: {tier}\n"
        f"Strategy: {strategy}\n"
        f"Phase: [bold {phase_color}]{phase}[/bold {phase_color}]",
        title="Rollout Status",
    ))

    meta = Table(show_header=False, box=None)
    meta.add_column(style="cyan")
    meta.add_column()
    meta.add_row("Stable Revision", str(result.get("stableRevision") or "-"))
    meta.add_row("Canary Revision", str(result.get("canaryRevision") or "-"))
    meta.add_row("Active Service", result.get("activeService") or "-")
    meta.add_row("Preview Service", result.get("previewService") or "-")
    current_step = result.get("currentStep")
    total_steps = result.get("totalSteps")
    if current_step is not None:
        step_display = f"{current_step}"
        if total_steps is not None:
            step_display += f" / {total_steps}"
        meta.add_row("Current Step", step_display)
    else:
        meta.add_row("Current Step", "-")
    meta.add_row("Message", result.get("message") or "-")
    console.print(meta)


def _rollout_action(action: str):
    @click.argument("team_slug")
    @click.argument("app_name")
    @click.option(
        "--tier",
        type=click.Choice(["dev", "staging", "production"]),
        default="production",
        show_default=True,
    )
    @pass_client
    def _cmd(client: DevExClient, team_slug: str, app_name: str, tier: str) -> None:
        _rollout_request(
            client,
            "POST",
            f"/teams/{team_slug}/applications/{app_name}/rollout/{action}",
            tier,
        )
        print_success(f"Rollout {action} triggered for '{app_name}' ({tier}).")
    return _cmd


rollout.command("promote")(_rollout_action("promote"))
rollout.command("pause")(_rollout_action("pause"))
rollout.command("abort")(_rollout_action("abort"))
