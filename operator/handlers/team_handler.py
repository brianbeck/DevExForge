"""Kopf handlers for the Team custom resource."""

import datetime
import logging

import kopf
from kubernetes.client.exceptions import ApiException

from helpers import get_k8s_clients

logger = logging.getLogger("devexforge.team")

GROUP = "devexforge.brianbeck.net"
VERSION = "v1alpha1"
PLURAL_TEAMS = "teams"
PLURAL_ENVIRONMENTS = "environments"


@kopf.on.create(GROUP, VERSION, PLURAL_TEAMS)
async def team_create(spec, name, namespace, patch, **_kwargs):
    """Handle Team creation: set status to Active and count environments."""
    logger.info("Creating Team %s", name)

    _, _, custom_api, _ = get_k8s_clients()

    env_count = _count_environments(custom_api, name)

    patch.status["phase"] = "Active"
    patch.status["environmentCount"] = env_count
    patch.status["conditions"] = [
        {
            "type": "Ready",
            "status": "True",
            "reason": "TeamCreated",
            "message": "Team created successfully",
            "lastTransitionTime": _now_iso(),
        },
    ]

    logger.info("Team %s created with %d environments", name, env_count)


@kopf.on.update(GROUP, VERSION, PLURAL_TEAMS)
async def team_update(spec, name, namespace, old, new, diff, patch, **_kwargs):
    """Handle Team update: re-count environments and trigger RBAC re-reconciliation if members changed."""
    logger.info("Updating Team %s", name)

    _, _, custom_api, _ = get_k8s_clients()

    env_count = _count_environments(custom_api, name)
    patch.status["environmentCount"] = env_count

    members_changed = any(
        field_path[0] == "spec" and len(field_path) > 1 and field_path[1] == "members"
        for op, field_path, old_val, new_val in diff
    )

    if members_changed:
        logger.info("Members changed for Team %s, triggering RBAC re-reconciliation", name)
        _annotate_environments_for_reconcile(custom_api, name)

    patch.status["conditions"] = [
        {
            "type": "Ready",
            "status": "True",
            "reason": "TeamUpdated",
            "message": "Team updated successfully",
            "lastTransitionTime": _now_iso(),
        },
    ]

    logger.info("Team %s updated, %d environments", name, env_count)


@kopf.on.delete(GROUP, VERSION, PLURAL_TEAMS)
async def team_delete(spec, name, namespace, **_kwargs):
    """Handle Team deletion: delete all associated Environment CRs."""
    logger.info("Deleting Team %s", name)

    _, _, custom_api, _ = get_k8s_clients()

    try:
        environments = custom_api.list_cluster_custom_object(
            group=GROUP,
            version=VERSION,
            plural=PLURAL_ENVIRONMENTS,
            label_selector=f"devexforge.brianbeck.net/team={name}",
        )
    except ApiException as e:
        if e.status == 404:
            logger.info("No Environment CRD found, nothing to clean up")
            return
        raise

    for env in environments.get("items", []):
        env_name = env["metadata"]["name"]
        env_ns = env["metadata"].get("namespace", "default")
        logger.info("Deleting Environment %s/%s for Team %s", env_ns, env_name, name)
        try:
            custom_api.delete_namespaced_custom_object(
                group=GROUP,
                version=VERSION,
                plural=PLURAL_ENVIRONMENTS,
                namespace=env_ns,
                name=env_name,
            )
        except ApiException as e:
            if e.status == 404:
                logger.warning("Environment %s already deleted", env_name)
            else:
                raise

    logger.info("Team %s deleted", name)


def _count_environments(custom_api, team_name: str) -> int:
    """Count Environment CRs belonging to a team."""
    try:
        environments = custom_api.list_cluster_custom_object(
            group=GROUP,
            version=VERSION,
            plural=PLURAL_ENVIRONMENTS,
            label_selector=f"devexforge.brianbeck.net/team={team_name}",
        )
        return len(environments.get("items", []))
    except ApiException as e:
        if e.status == 404:
            return 0
        raise


def _annotate_environments_for_reconcile(custom_api, team_name: str) -> None:
    """Annotate all Environment CRs for a team to trigger RBAC re-reconciliation."""
    try:
        environments = custom_api.list_cluster_custom_object(
            group=GROUP,
            version=VERSION,
            plural=PLURAL_ENVIRONMENTS,
            label_selector=f"devexforge.brianbeck.net/team={team_name}",
        )
    except ApiException as e:
        if e.status == 404:
            return
        raise

    timestamp = _now_iso()
    for env in environments.get("items", []):
        env_name = env["metadata"]["name"]
        env_ns = env["metadata"].get("namespace", "default")
        try:
            custom_api.patch_namespaced_custom_object(
                group=GROUP,
                version=VERSION,
                plural=PLURAL_ENVIRONMENTS,
                namespace=env_ns,
                name=env_name,
                body={
                    "metadata": {
                        "annotations": {
                            "devexforge.brianbeck.net/reconcile-trigger": timestamp,
                        },
                    },
                },
            )
            logger.info("Annotated Environment %s/%s for reconciliation", env_ns, env_name)
        except ApiException as e:
            if e.status == 404:
                logger.warning("Environment %s/%s not found during annotation", env_ns, env_name)
            else:
                raise


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
