import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TEAMS_URL = "/api/v1/teams"


def _team_payload(name: str = "Platform Team", **overrides) -> dict:
    body = {"displayName": name}
    body.update(overrides)
    return body


# ---- CRUD -----------------------------------------------------------------

async def test_create_team(client: AsyncClient):
    resp = await client.post(TEAMS_URL, json=_team_payload("Platform Team"))
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "platform-team"
    assert data["displayName"] == "Platform Team"
    assert data["ownerEmail"] == "admin@company.com"
    assert data["memberCount"] == 1  # owner auto-added


async def test_create_team_slugify(client: AsyncClient):
    resp = await client.post(TEAMS_URL, json=_team_payload("My Cool Team!"))
    assert resp.status_code == 201
    assert resp.json()["slug"] == "my-cool-team"


async def test_create_team_duplicate_slug(client: AsyncClient):
    await client.post(TEAMS_URL, json=_team_payload("Dupe"))
    resp2 = await client.post(TEAMS_URL, json=_team_payload("Dupe"))
    assert resp2.status_code == 201
    assert resp2.json()["slug"] == "dupe-1"


async def test_list_teams(client: AsyncClient):
    await client.post(TEAMS_URL, json=_team_payload("Team Alpha"))
    await client.post(TEAMS_URL, json=_team_payload("Team Beta"))
    resp = await client.get(TEAMS_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["teams"]) == 2


async def test_get_team(client: AsyncClient):
    create_resp = await client.post(TEAMS_URL, json=_team_payload("Lookup Team"))
    slug = create_resp.json()["slug"]

    resp = await client.get(f"{TEAMS_URL}/{slug}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == slug


async def test_get_team_not_found(client: AsyncClient):
    resp = await client.get(f"{TEAMS_URL}/nonexistent")
    assert resp.status_code == 404


async def test_update_team(client: AsyncClient):
    create_resp = await client.post(TEAMS_URL, json=_team_payload("Updatable"))
    slug = create_resp.json()["slug"]

    resp = await client.patch(
        f"{TEAMS_URL}/{slug}",
        json={"description": "Updated description"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated description"


async def test_delete_team(client: AsyncClient):
    create_resp = await client.post(TEAMS_URL, json=_team_payload("Deletable"))
    slug = create_resp.json()["slug"]

    resp = await client.delete(f"{TEAMS_URL}/{slug}")
    assert resp.status_code == 204

    get_resp = await client.get(f"{TEAMS_URL}/{slug}")
    assert get_resp.status_code == 404


# ---- Authorization -------------------------------------------------------

async def test_create_team_requires_team_leader_role(developer_client: AsyncClient):
    resp = await developer_client.post(
        TEAMS_URL, json=_team_payload("Unauthorized")
    )
    assert resp.status_code == 403
