"""Environment profile management for DevExForge CLI.

Profiles are stored in ~/.devexforge/config.yaml:

    active: stage
    profiles:
      stage:
        api_url: https://devexforge-api-stage.brianbeck.net
        keycloak_url: https://keycloak-stage.brianbeck.net
        insecure: true
        token: eyJhbG...
      prod:
        api_url: https://devexforge-api.brianbeck.net
        keycloak_url: https://keycloak.brianbeck.net
        insecure: true
        token: eyJhbG...
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR = Path.home() / ".devexforge"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def _load_config() -> dict[str, Any]:
    """Load the config file, returning empty structure if missing."""
    if not CONFIG_FILE.exists():
        return {"active": "", "profiles": {}}
    try:
        with open(CONFIG_FILE) as f:
            data = yaml.safe_load(f) or {}
        data.setdefault("active", "")
        data.setdefault("profiles", {})
        return data
    except Exception:
        return {"active": "", "profiles": {}}


def _save_config(config: dict[str, Any]) -> None:
    """Save the config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    # Restrict permissions since it contains tokens
    CONFIG_FILE.chmod(0o600)


def list_profiles() -> dict[str, dict[str, Any]]:
    """Return all profiles."""
    return _load_config()["profiles"]


def get_active_profile_name() -> str:
    """Return the name of the active profile, or empty string."""
    return _load_config()["active"]


def get_profile(name: str) -> dict[str, Any] | None:
    """Return a profile by name, or None."""
    return _load_config()["profiles"].get(name)


def get_active_profile() -> tuple[str, dict[str, Any]] | None:
    """Return (name, profile) for the active profile, or None."""
    config = _load_config()
    name = config["active"]
    if not name:
        return None
    profile = config["profiles"].get(name)
    if not profile:
        return None
    return name, profile


def save_profile(name: str, profile: dict[str, Any]) -> None:
    """Save or update a profile."""
    config = _load_config()
    config["profiles"][name] = profile
    _save_config(config)


def set_active(name: str) -> bool:
    """Set the active profile. Returns False if profile doesn't exist."""
    config = _load_config()
    if name not in config["profiles"]:
        return False
    config["active"] = name
    _save_config(config)
    return True


def delete_profile(name: str) -> bool:
    """Delete a profile. Returns False if it doesn't exist."""
    config = _load_config()
    if name not in config["profiles"]:
        return False
    del config["profiles"][name]
    if config["active"] == name:
        config["active"] = ""
    _save_config(config)
    return True


def update_token(name: str, token: str) -> bool:
    """Update the token for an existing profile."""
    config = _load_config()
    if name not in config["profiles"]:
        return False
    config["profiles"][name]["token"] = token
    _save_config(config)
    return True
