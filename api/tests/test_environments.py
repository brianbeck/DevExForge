import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TEAMS_URL = "/api/v1/teams"


async def _create_team(client: AsyncClient, name: str = "Env Team") -> str:
    resp = await client.post(TEAMS_URL, json={"displayName": name})
    assert resp.status_code == 201
    return resp.json()["slug"]


def _envs_url(slug: str) -> str:
    return f"{TEAMS_URL}/{slug}/environments"


# ---- Create ---------------------------------------------------------------

async def test_create_dev_environment(client: AsyncClient):
    slug = await _create_team(client)
    resp = await client.post(_envs_url(slug), json={"tier": "dev"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["namespaceName"] == f"{slug}-dev"
    assert data["phase"] == "Pending"
    # Dev floor defaults should be applied
    policies = data["policies"]
    assert policies["requireNonRoot"] is False
    assert policies["maxCriticalCVEs"] == 5
    assert policies["maxHighCVEs"] == 20


async def test_create_production_environment(client: AsyncClient):
    slug = await _create_team(client)
    resp = await client.post(_envs_url(slug), json={"tier": "production"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["namespaceName"] == f"{slug}-production"
    policies = data["policies"]
    assert policies["requireNonRoot"] is True
    assert policies["requireReadOnlyRoot"] is True
    assert policies["maxCriticalCVEs"] == 0
    assert policies["maxHighCVEs"] == 0
    assert policies["requireResourceLimits"] is True


async def test_create_duplicate_environment(client: AsyncClient):
    slug = await _create_team(client)
    resp1 = await client.post(_envs_url(slug), json={"tier": "dev"})
    assert resp1.status_code == 201

    resp2 = await client.post(_envs_url(slug), json={"tier": "dev"})
    assert resp2.status_code == 409


# ---- Policy floor enforcement ---------------------------------------------

async def test_policy_floor_enforcement_non_root(client: AsyncClient):
    """Production tier rejects requireNonRoot=false."""
    slug = await _create_team(client)
    resp = await client.post(
        _envs_url(slug),
        json={
            "tier": "production",
            "policies": {
                "requireNonRoot": False,
                "requireReadOnlyRoot": True,
                "maxCriticalCVEs": 0,
                "maxHighCVEs": 0,
                "requireResourceLimits": True,
            },
        },
    )
    assert resp.status_code == 409
    assert "requireNonRoot" in resp.json()["detail"]


async def test_policy_floor_enforcement_high_cves(client: AsyncClient):
    """Production tier rejects maxHighCVEs > 0."""
    slug = await _create_team(client)
    resp = await client.post(
        _envs_url(slug),
        json={
            "tier": "production",
            "policies": {
                "requireNonRoot": True,
                "requireReadOnlyRoot": True,
                "maxCriticalCVEs": 0,
                "maxHighCVEs": 10,
                "requireResourceLimits": True,
            },
        },
    )
    assert resp.status_code == 409
    assert "maxHighCVEs" in resp.json()["detail"]


# ---- Update / Delete / List -----------------------------------------------

async def test_update_environment(client: AsyncClient):
    slug = await _create_team(client)
    await client.post(_envs_url(slug), json={"tier": "dev"})

    resp = await client.patch(
        f"{_envs_url(slug)}/dev",
        json={
            "resourceQuota": {
                "cpuRequest": "1",
                "cpuLimit": "4",
                "memoryRequest": "1Gi",
                "memoryLimit": "4Gi",
                "pods": 50,
                "services": 20,
                "persistentVolumeClaims": 10,
            }
        },
    )
    assert resp.status_code == 200
    rq = resp.json()["resourceQuota"]
    assert rq["cpuRequest"] == "1"
    assert rq["pods"] == 50


async def test_delete_environment(client: AsyncClient):
    slug = await _create_team(client)
    await client.post(_envs_url(slug), json={"tier": "dev"})

    resp = await client.delete(f"{_envs_url(slug)}/dev")
    assert resp.status_code == 204

    get_resp = await client.get(f"{_envs_url(slug)}/dev")
    assert get_resp.status_code == 404


async def test_list_environments(client: AsyncClient):
    slug = await _create_team(client)
    await client.post(_envs_url(slug), json={"tier": "dev"})
    await client.post(_envs_url(slug), json={"tier": "staging"})

    resp = await client.get(_envs_url(slug))
    assert resp.status_code == 200
    tiers = {e["tier"] for e in resp.json()}
    assert tiers == {"dev", "staging"}
