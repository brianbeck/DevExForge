"""DevExForge CLI entry point."""

from __future__ import annotations

import click

from devex.client import DevExClient
from devex.commands.app import app
from devex.commands.env import env
from devex.commands.gates import gates
from devex.commands.login import login, profile
from devex.commands.members import members
from devex.commands.promote import promote
from devex.commands.rollout import rollout
from devex.commands.team import team
from devex.profiles import get_active_profile


@click.group()
@click.option(
    "--api-url",
    envvar="DEVEXFORGE_API_URL",
    default=None,
    help="Override API URL (default: from active profile).",
)
@click.option(
    "--token",
    envvar="DEVEXFORGE_TOKEN",
    default=None,
    help="Override bearer token (default: from active profile).",
)
@click.option(
    "--insecure", "-k",
    is_flag=True,
    envvar="DEVEXFORGE_INSECURE",
    default=None,
    help="Disable TLS certificate verification.",
)
@click.version_option(package_name="devexforge-cli")
@click.pass_context
def cli(ctx: click.Context, api_url: str | None, token: str | None, insecure: bool | None) -> None:
    """DevExForge -- developer self-service CLI."""
    ctx.ensure_object(dict)

    # Load from active profile if not overridden by flags/env
    active = get_active_profile()
    if active:
        _name, p = active
        api_url = api_url or p.get("api_url")
        token = token or p.get("token")
        if insecure is None:
            insecure = p.get("insecure", False)

    ctx.obj = DevExClient(
        base_url=api_url,
        token=token,
        insecure=bool(insecure),
    )


# Register commands
cli.add_command(login)
cli.add_command(profile)
cli.add_command(team)
cli.add_command(env)
cli.add_command(app)
cli.add_command(promote)
cli.add_command(rollout)
cli.add_command(gates)

# Nest members under team
team.add_command(members)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
