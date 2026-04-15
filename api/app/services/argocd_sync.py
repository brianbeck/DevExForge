"""Background task that syncs Argo CD Application status into the DevExForge database."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import database
from app.models.application import ApplicationDeployment, ApplicationDeploymentEvent
from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 30
ADVISORY_LOCK_KEY = 0xDE7EF07E  # arbitrary stable key for the sync lock

_task: asyncio.Task | None = None


async def start_sync_loop() -> None:
    """Start the background sync loop. Idempotent."""
    global _task
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_run_loop(), name="argocd-sync")
    logger.info("Started Argo CD sync loop (interval=%ds)", SYNC_INTERVAL_SECONDS)


async def stop_sync_loop() -> None:
    """Stop the background sync loop. Idempotent."""
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    finally:
        _task = None
    logger.info("Stopped Argo CD sync loop")


async def _run_loop() -> None:
    """Main loop body."""
    while True:
        try:
            await _sync_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Argo CD sync cycle failed: %s", e)
        try:
            await asyncio.sleep(SYNC_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise


async def _sync_once() -> None:
    """One sync cycle. Acquires advisory lock to ensure single-writer."""
    if database.async_session_factory is None:
        logger.warning("Database not initialized; skipping sync cycle")
        return

    async with database.async_session_factory() as session:
        # Try to acquire advisory lock. If the backend doesn't support
        # pg_try_advisory_lock (e.g. SQLite in tests), silently skip the cycle.
        try:
            result = await session.execute(
                text("SELECT pg_try_advisory_lock(:key)").bindparams(
                    key=ADVISORY_LOCK_KEY
                )
            )
            acquired = result.scalar()
        except Exception as e:
            logger.warning(
                "Advisory lock not supported by database backend; skipping sync cycle: %s",
                e,
            )
            try:
                await session.rollback()
            except Exception:
                pass
            return

        if not acquired:
            logger.debug("Advisory lock held by another replica; skipping sync cycle")
            return

        try:
            await _sync_deployments(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Always release the lock
            try:
                await session.execute(
                    text("SELECT pg_advisory_unlock(:key)").bindparams(
                        key=ADVISORY_LOCK_KEY
                    )
                )
                await session.commit()
            except Exception as e:
                logger.warning("Failed to release advisory lock: %s", e)


async def _sync_deployments(session: AsyncSession) -> None:
    """Fetch all deployments from DB, group by cluster, refresh each from Argo CD."""
    stmt = select(ApplicationDeployment).options(
        selectinload(ApplicationDeployment.environment)
    )
    result = await session.execute(stmt)
    deployments = list(result.scalars().all())

    if not deployments:
        return

    # Group by (cluster, namespace_name)
    by_cluster: dict[str, list[ApplicationDeployment]] = {}
    for d in deployments:
        if d.environment is None:
            continue
        try:
            cluster = k8s_service.cluster_for_tier(d.environment.tier)
        except ValueError:
            continue
        by_cluster.setdefault(cluster, []).append(d)

    # For each cluster, fetch all DevExForge-managed Argo CD Applications in one call
    for cluster, cluster_deployments in by_cluster.items():
        try:
            apps = k8s_service.list_argo_applications(
                cluster,
                namespace="argocd",
                label_selector="devexforge.brianbeck.net/managed-by=devexforge",
            )
        except Exception as e:
            logger.warning(
                "Failed to list Argo CD applications in %s: %s", cluster, e
            )
            continue

        apps_by_name: dict[str, dict] = {}
        for a in apps:
            meta = a.get("metadata") if isinstance(a, dict) else None
            if not meta:
                continue
            name = meta.get("name")
            if name:
                apps_by_name[name] = a

        for deployment in cluster_deployments:
            try:
                app = apps_by_name.get(deployment.argocd_app_name)
                if app is None:
                    _update_missing(deployment)
                    continue
                _update_from_argocd(deployment, app, session)
            except Exception as e:
                logger.exception(
                    "Failed to update deployment %s: %s", deployment.id, e
                )


def _extract_status(app: dict) -> dict:
    """Parse Argo CD Application status into the fields we care about."""
    status = app.get("status", {}) or {}
    health = status.get("health", {}) or {}
    sync = status.get("sync", {}) or {}
    summary = status.get("summary", {}) or {}
    op_state = status.get("operationState", {}) or {}

    image_tag: str | None = None
    images = summary.get("images", []) or []
    if images:
        first = images[0]
        if isinstance(first, str) and ":" in first:
            image_tag = first.rsplit(":", 1)[-1]

    return {
        "health_status": health.get("status") or "Unknown",
        "sync_status": sync.get("status") or "Unknown",
        "last_sync_at": op_state.get("finishedAt"),
        "image_tag": image_tag,
        "raw": app,
    }


def _update_missing(deployment: ApplicationDeployment) -> None:
    """Handle case where Argo CD Application no longer exists."""
    if deployment.health_status != "Missing":
        deployment.health_status = "Missing"
        deployment.sync_status = "Unknown"
        deployment.last_synced_at = datetime.now(timezone.utc)


def _update_from_argocd(
    deployment: ApplicationDeployment,
    app: dict,
    session: AsyncSession,
) -> None:
    """Update a deployment row from an Argo CD Application dict and emit events on status changes."""
    parsed = _extract_status(app)
    new_health = parsed["health_status"]
    new_sync = parsed["sync_status"]
    old_health = deployment.health_status

    deployment.health_status = new_health
    deployment.sync_status = new_sync
    deployment.last_synced_at = datetime.now(timezone.utc)
    deployment.raw_status = parsed["raw"]

    new_image_tag = parsed["image_tag"]
    if new_image_tag and new_image_tag != deployment.image_tag:
        deployment.image_tag = new_image_tag

    if old_health != new_health:
        event = ApplicationDeploymentEvent(
            deployment_id=deployment.id,
            event_type="status_changed",
            from_version=old_health or "",
            to_version=new_health,
            actor="system",
            details={"from": old_health, "to": new_health},
        )
        session.add(event)
