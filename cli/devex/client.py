"""API client for DevExForge."""

from __future__ import annotations

import os
import sys
from typing import Any

import click
import httpx

from devex.output import print_error

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 30.0


class DevExClient:
    """HTTP client for the DevExForge API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        insecure: bool = False,
    ) -> None:
        raw_url = (
            base_url
            or os.environ.get("DEVEXFORGE_API_URL")
            or DEFAULT_API_URL
        ).rstrip("/")
        # Ensure base URL includes the API prefix
        self.base_url = raw_url if raw_url.endswith("/api/v1") else f"{raw_url}/api/v1"
        self.token = token or os.environ.get("DEVEXFORGE_TOKEN")
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
            verify=not insecure,
        )

    # -- low-level helpers ---------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Execute a request and return parsed JSON, handling errors."""
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.ConnectError:
            print_error(f"Could not connect to the API at {self.base_url}")
            print_error("Make sure the DevExForge API is running.")
            sys.exit(1)
        except httpx.TimeoutException:
            print_error("Request timed out. Try again or check the API.")
            sys.exit(1)
        except httpx.HTTPError as exc:
            print_error(f"HTTP error: {exc}")
            sys.exit(1)

        if response.status_code == 204:
            return None

        try:
            body = response.json()
        except Exception:
            body = None

        if response.is_success:
            return body

        # Error responses
        detail = ""
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("message") or ""
        if not detail:
            detail = response.text or f"HTTP {response.status_code}"
        print_error(f"[{response.status_code}] {detail}")
        sys.exit(1)

    # -- convenience wrappers ------------------------------------------------

    def get(self, path: str, **params: Any) -> Any:
        """Send a GET request."""
        return self._request("GET", path, params=params)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        """Send a POST request with a JSON body."""
        return self._request("POST", path, json=payload or {})

    def patch(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        """Send a PATCH request with a JSON body."""
        return self._request("PATCH", path, json=payload or {})

    def delete(self, path: str) -> Any:
        """Send a DELETE request."""
        return self._request("DELETE", path)


# Click helpers to thread the client through context --------------------------

pass_client = click.make_pass_decorator(DevExClient, ensure=True)
