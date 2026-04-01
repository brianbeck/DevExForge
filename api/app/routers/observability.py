"""Observability endpoints: metrics, dashboards, resource usage."""
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import CurrentUser, get_current_user
from app.services import environment_service
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/teams/{slug}/environments/{tier}",
    tags=["observability"],
)


def _prometheus_url(cluster: str) -> str:
    if cluster == "beck-prod":
        return settings.PROMETHEUS_PROD_URL
    return settings.PROMETHEUS_STAGE_URL


def _grafana_url(cluster: str) -> str:
    if cluster == "beck-prod":
        return settings.GRAFANA_PROD_URL
    return settings.GRAFANA_STAGE_URL


async def _get_env_namespace(db: AsyncSession, slug: str, tier: str) -> tuple[str, str]:
    try:
        env = await environment_service.get_environment(db, slug, tier)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    cluster = k8s_service.cluster_for_tier(tier)
    return env.namespace_name, cluster


@router.get("/resource-usage")
async def get_resource_usage(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get current resource usage vs quota for an environment."""
    namespace, cluster = await _get_env_namespace(db, slug, tier)
    try:
        quota_data = k8s_service.get_resource_quota_usage(cluster, namespace)
    except Exception:
        logger.warning("Failed to fetch resource usage for %s", namespace, exc_info=True)
        quota_data = {"quotas": []}
    return {"namespace": namespace, "cluster": cluster, **quota_data}


@router.get("/metrics")
async def get_metrics(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    query: str = "",
) -> dict:
    """Proxy a PromQL query to Prometheus, scoped to the environment namespace.

    If no query is provided, returns standard namespace metrics:
    CPU usage, memory usage, and pod count.
    """
    namespace, cluster = await _get_env_namespace(db, slug, tier)
    prom_url = _prometheus_url(cluster)

    if not query:
        # Default: return standard namespace metrics
        queries = {
            "cpuUsage": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m]))',
            "memoryUsage": f'sum(container_memory_working_set_bytes{{namespace="{namespace}"}})',
            "podCount": f'count(kube_pod_info{{namespace="{namespace}"}})',
        }
        results = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, promql in queries.items():
                try:
                    resp = await client.get(
                        f"{prom_url}/api/v1/query",
                        params={"query": promql},
                    )
                    data = resp.json()
                    result = data.get("data", {}).get("result", [])
                    if result:
                        results[name] = result[0].get("value", [None, "0"])[1]
                    else:
                        results[name] = "0"
                except Exception:
                    logger.warning("Prometheus query failed for %s: %s", name, promql)
                    results[name] = None
        return {"namespace": namespace, "metrics": results}

    # Custom query - inject namespace filter
    if "namespace" not in query:
        query = query.replace("}", f', namespace="{namespace}"}}', 1)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{prom_url}/api/v1/query",
                params={"query": query},
            )
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Prometheus query failed: {e}")


@router.get("/dashboards")
async def get_dashboards(
    slug: str,
    tier: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Return Grafana dashboard URLs pre-filtered to the environment namespace."""
    namespace, cluster = await _get_env_namespace(db, slug, tier)
    grafana_url = _grafana_url(cluster)

    return {
        "namespace": namespace,
        "dashboards": [
            {
                "name": "Namespace Overview",
                "url": f"{grafana_url}/d/namespace-overview?var-namespace={namespace}",
            },
            {
                "name": "Pod Resources",
                "url": f"{grafana_url}/d/pod-resources?var-namespace={namespace}",
            },
            {
                "name": "Network Traffic",
                "url": f"{grafana_url}/d/network-traffic?var-namespace={namespace}",
            },
            {
                "name": "Workload Overview",
                "url": f"{grafana_url}/d/workload-overview?var-namespace={namespace}",
            },
        ],
    }
