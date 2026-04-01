import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TEAMS_URL = "/api/v1/teams"


async def _create_team(client: AsyncClient, name: str = "Members Team") -> str:
    """Helper: create a team and return its slug."""
    resp = await client.post(TEAMS_URL, json={"displayName": name})
    assert resp.status_code == 201
    return resp.json()["slug"]


def _members_url(slug: str) -> str:
    return f"{TEAMS_URL}/{slug}/members"


# ---- Member CRUD ----------------------------------------------------------

async def test_add_member(client: AsyncClient):
    slug = await _create_team(client)
    resp = await client.post(
        _members_url(slug),
        json={"email": "dev@company.com", "role": "developer"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "dev@company.com"
    assert data["role"] == "developer"


async def test_list_members(client: AsyncClient):
    slug = await _create_team(client)
    # Owner is already a member
    await client.post(
        _members_url(slug),
        json={"email": "dev@company.com", "role": "developer"},
    )

    resp = await client.get(_members_url(slug))
    assert resp.status_code == 200
    members = resp.json()
    emails = {m["email"] for m in members}
    # Owner (admin@company.com) + added member
    assert "admin@company.com" in emails
    assert "dev@company.com" in emails
    assert len(members) == 2


async def test_update_member_role(client: AsyncClient):
    slug = await _create_team(client)
    await client.post(
        _members_url(slug),
        json={"email": "dev@company.com", "role": "developer"},
    )

    resp = await client.patch(
        f"{_members_url(slug)}/dev@company.com",
        json={"role": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


async def test_remove_member(client: AsyncClient):
    slug = await _create_team(client)
    await client.post(
        _members_url(slug),
        json={"email": "removeme@company.com", "role": "viewer"},
    )

    resp = await client.delete(f"{_members_url(slug)}/removeme@company.com")
    assert resp.status_code == 204

    # Verify the member is gone
    list_resp = await client.get(_members_url(slug))
    emails = {m["email"] for m in list_resp.json()}
    assert "removeme@company.com" not in emails


async def test_cannot_remove_owner(client: AsyncClient):
    slug = await _create_team(client)
    # The owner is admin@company.com
    resp = await client.delete(f"{_members_url(slug)}/admin@company.com")
    assert resp.status_code == 400
    assert "owner" in resp.json()["detail"].lower()
