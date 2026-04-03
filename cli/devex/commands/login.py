"""Login and environment profile commands."""

from __future__ import annotations

import sys

import click
import httpx

from devex.output import print_error, print_success, print_table
from devex.profiles import (
    delete_profile,
    get_active_profile,
    get_active_profile_name,
    get_profile,
    list_profiles,
    save_profile,
    set_active,
    update_token,
)


@click.group()
def profile() -> None:
    """Manage environment profiles (stage, prod, etc.)."""


@profile.command("add")
@click.argument("name")
@click.option(
    "--api-url",
    prompt="API URL",
    help="Base URL of the DevExForge API.",
)
@click.option(
    "--keycloak-url",
    prompt="Keycloak URL",
    help="Keycloak server URL.",
)
@click.option(
    "--insecure", "-k",
    is_flag=True,
    default=False,
    help="Disable TLS certificate verification.",
)
@click.option(
    "--set-active/--no-set-active",
    default=True,
    help="Set this as the active profile.",
)
def profile_add(
    name: str,
    api_url: str,
    keycloak_url: str,
    insecure: bool,
    set_active: bool,
) -> None:
    """Add a new environment profile.

    Example: devex profile add stage
    """
    save_profile(name, {
        "api_url": api_url,
        "keycloak_url": keycloak_url,
        "insecure": insecure,
        "token": "",
    })
    if set_active:
        from devex.profiles import set_active as do_set_active
        do_set_active(name)
    print_success(f"Profile '{name}' saved{' and set as active' if set_active else ''}.")


@profile.command("list")
def profile_list() -> None:
    """List all environment profiles."""
    profiles = list_profiles()
    active = get_active_profile_name()

    if not profiles:
        click.echo("No profiles configured. Run: devex profile add <name>")
        return

    headers = ["", "Name", "API URL", "Keycloak URL", "Insecure", "Logged In"]
    rows = []
    for name, p in profiles.items():
        marker = "*" if name == active else ""
        rows.append([
            marker,
            name,
            p.get("api_url", ""),
            p.get("keycloak_url", ""),
            "yes" if p.get("insecure") else "no",
            "yes" if p.get("token") else "no",
        ])
    print_table(headers, rows)


@profile.command("use")
@click.argument("name")
def profile_use(name: str) -> None:
    """Switch to a different profile.

    Example: devex profile use prod
    """
    if not set_active(name):
        print_error(f"Profile '{name}' not found. Run: devex profile list")
        sys.exit(1)
    print_success(f"Switched to profile '{name}'.")


@profile.command("remove")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure?")
def profile_remove(name: str) -> None:
    """Remove an environment profile."""
    if not delete_profile(name):
        print_error(f"Profile '{name}' not found.")
        sys.exit(1)
    print_success(f"Profile '{name}' removed.")


@profile.command("show")
@click.argument("name", required=False)
def profile_show(name: str | None) -> None:
    """Show details of a profile (defaults to active)."""
    if name is None:
        result = get_active_profile()
        if result is None:
            print_error("No active profile. Run: devex profile use <name>")
            sys.exit(1)
        name, p = result
    else:
        p = get_profile(name)
        if p is None:
            print_error(f"Profile '{name}' not found.")
            sys.exit(1)

    active = get_active_profile_name()
    click.echo(f"Profile: {name}{' (active)' if name == active else ''}")
    click.echo(f"  API URL:      {p.get('api_url', '')}")
    click.echo(f"  Keycloak URL: {p.get('keycloak_url', '')}")
    click.echo(f"  Insecure:     {'yes' if p.get('insecure') else 'no'}")
    click.echo(f"  Logged In:    {'yes' if p.get('token') else 'no'}")


@click.command()
@click.option("--profile-name", "-p", default=None, help="Profile to log in to (defaults to active).")
@click.option("--username", prompt="Username", help="Keycloak username.")
@click.option("--password", prompt="Password", hide_input=True, help="Keycloak password.")
@click.option("--realm", default="teams", show_default=True, help="Keycloak realm.")
@click.option("--client-id", default="devexforge-portal", show_default=True, help="Keycloak client ID.")
def login(
    profile_name: str | None,
    username: str,
    password: str,
    realm: str,
    client_id: str,
) -> None:
    """Log in to the active (or specified) environment profile.

    Authenticates with Keycloak and stores the token in the profile.
    """
    if profile_name:
        p = get_profile(profile_name)
        if p is None:
            print_error(f"Profile '{profile_name}' not found. Run: devex profile list")
            sys.exit(1)
        name = profile_name
    else:
        result = get_active_profile()
        if result is None:
            print_error("No active profile. Set one up first:")
            print_error("  devex profile add stage")
            sys.exit(1)
        name, p = result

    keycloak_url = p.get("keycloak_url", "")
    insecure = p.get("insecure", False)

    if not keycloak_url:
        print_error(f"Profile '{name}' has no keycloak_url configured.")
        sys.exit(1)

    token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"

    try:
        response = httpx.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": client_id,
                "username": username,
                "password": password,
            },
            verify=not insecure,
            timeout=10.0,
        )
    except httpx.ConnectError:
        print_error(f"Could not connect to Keycloak at {keycloak_url}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to connect: {e}")
        sys.exit(1)

    if not response.is_success:
        try:
            detail = response.json().get("error_description", response.text)
        except Exception:
            detail = response.text
        print_error(f"Authentication failed: {detail}")
        sys.exit(1)

    token = response.json().get("access_token")
    if not token:
        print_error("No access token in response.")
        sys.exit(1)

    update_token(name, token)
    print_success(f"Logged in to '{name}' as {username}.")
