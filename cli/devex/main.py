"""DevExForge CLI entry point."""

from __future__ import annotations

import click

from devex.client import DevExClient
from devex.commands.env import env
from devex.commands.members import members
from devex.commands.team import team


@click.group()
@click.option(
    "--api-url",
    envvar="DEVEXFORGE_API_URL",
    default="http://localhost:8000",
    show_default=True,
    help="Base URL of the DevExForge API.",
)
@click.option(
    "--token",
    envvar="DEVEXFORGE_TOKEN",
    default=None,
    help="Bearer token for API authentication.",
)
@click.version_option(package_name="devexforge-cli")
@click.pass_context
def cli(ctx: click.Context, api_url: str, token: str | None) -> None:
    """DevExForge -- developer self-service CLI."""
    ctx.ensure_object(dict)
    ctx.obj = DevExClient(base_url=api_url, token=token)


# Register top-level command groups
cli.add_command(team)
cli.add_command(env)

# Nest members under team
team.add_command(members)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
