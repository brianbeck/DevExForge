"""Argo Rollouts service for blue-green and canary deployments.

Phase 2b: Argo Rollouts is installed in PlatformForge but WITHOUT a traffic
router plugin. Implications:
  - Blue-green relies on Kubernetes Service selector swap (instant cutover).
  - Canary `setWeight` is interpreted by the controller as a replica-count
    ratio, not HTTP traffic percentage. Precise traffic shifting is not
    available until a Gateway API / traffic router plugin is adopted.
"""

from __future__ import annotations

import logging
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from app.services.k8s_service import k8s_service

logger = logging.getLogger(__name__)

ROLLOUTS_GROUP = "argoproj.io"
ROLLOUTS_VERSION = "v1alpha1"
ROLLOUTS_PLURAL = "rollouts"
ROLLOUTS_CRD_NAME = "rollouts.argoproj.io"

DEFAULT_CANARY_STEPS: list[dict] = [
    {"setWeight": 20},
    {"pause": {}},
    {"setWeight": 50},
    {"pause": {}},
    {"setWeight": 80},
    {"pause": {}},
]

# Cache of cluster -> bool indicating whether the Rollouts CRD is installed.
_rollouts_available_cache: dict[str, bool] = {}


class RolloutsNotAvailable(Exception):
    """Raised when the Argo Rollouts CRDs are not installed on the target cluster."""


def _custom_api(cluster: str) -> client.CustomObjectsApi:
    # Reuse the CustomObjectsApi already configured for this cluster by k8s_service.
    return k8s_service._get_api(cluster)


def _apiextensions_api(cluster: str) -> client.ApiextensionsV1Api:
    custom = _custom_api(cluster)
    return client.ApiextensionsV1Api(api_client=custom.api_client)


async def check_rollouts_available(cluster: str) -> bool:
    """Check whether the Argo Rollouts CRD is installed on the target cluster.

    Result is cached per-cluster in a module-level dict.
    """
    cached = _rollouts_available_cache.get(cluster)
    if cached is not None:
        return cached

    try:
        api = _apiextensions_api(cluster)
        api.read_custom_resource_definition(name=ROLLOUTS_CRD_NAME)
        _rollouts_available_cache[cluster] = True
        return True
    except ApiException as e:
        if e.status == 404:
            _rollouts_available_cache[cluster] = False
            return False
        logger.warning(
            "Failed to query Rollouts CRD on cluster '%s': %s", cluster, e.reason
        )
        return False
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(
            "Unexpected error checking Rollouts on cluster '%s': %s", cluster, e
        )
        return False


def build_rollout_manifest(
    app: Any,
    target_namespace: str,
    image_tag: str,
    strategy: str,
    canary_steps: list[dict] | None = None,
    active_service: str | None = None,
    preview_service: str | None = None,
    image: str | None = None,
    replicas: int = 3,
) -> dict:
    """Build an argoproj.io/v1alpha1 Rollout CR for the given application.

    NOTE: The Application model stores a source/chart repo URL but not the
    container image repository. Callers SHOULD pass an explicit `image`
    argument. As a fallback we derive it from `app.repo_url:image_tag`, which
    is only a sensible default when the source repo URL happens to coincide
    with the container image repository. This assumption will need to be
    revisited once Application gains an explicit image_repo field.
    """
    if strategy == "rolling":
        raise ValueError(
            "Rolling updates do not use Argo Rollouts; deploy via a plain "
            "Deployment through an Argo CD Application instead."
        )
    if strategy not in ("bluegreen", "canary"):
        raise ValueError(f"Unsupported rollout strategy: {strategy}")

    container_image = image or f"{app.repo_url}:{image_tag}"

    labels = {
        "app": app.name,
        "devexforge.brianbeck.net/managed-by": "devexforge",
        "devexforge.brianbeck.net/application": app.name,
    }

    strategy_spec: dict
    if strategy == "bluegreen":
        if not active_service or not preview_service:
            raise ValueError(
                "Blue-green strategy requires active_service and preview_service"
            )
        strategy_spec = {
            "blueGreen": {
                "activeService": active_service,
                "previewService": preview_service,
                "autoPromotionEnabled": False,
                "scaleDownDelaySeconds": 30,
                "prePromotionAnalysis": None,
            }
        }
    else:
        # NOTE: without a traffic router, setWeight is interpreted as replica
        # ratio, not HTTP traffic percentage.
        strategy_spec = {
            "canary": {
                "steps": canary_steps or DEFAULT_CANARY_STEPS,
            }
        }

    manifest: dict = {
        "apiVersion": f"{ROLLOUTS_GROUP}/{ROLLOUTS_VERSION}",
        "kind": "Rollout",
        "metadata": {
            "name": app.name,
            "namespace": target_namespace,
            "labels": labels,
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": app.name}},
            "template": {
                "metadata": {"labels": {"app": app.name}},
                "spec": {
                    "containers": [
                        {
                            "name": app.name,
                            "image": container_image,
                        }
                    ],
                },
            },
            "strategy": strategy_spec,
        },
    }
    return manifest


async def create_or_update_rollout(
    cluster: str, namespace: str, manifest: dict
) -> dict:
    """Create or patch a Rollout CR on the specified cluster/namespace."""
    if not await check_rollouts_available(cluster):
        raise RolloutsNotAvailable(
            f"Argo Rollouts CRDs are not installed on cluster '{cluster}'"
        )

    api = _custom_api(cluster)
    name = manifest["metadata"]["name"]
    try:
        existing = api.get_namespaced_custom_object(
            group=ROLLOUTS_GROUP,
            version=ROLLOUTS_VERSION,
            namespace=namespace,
            plural=ROLLOUTS_PLURAL,
            name=name,
        )
        manifest["metadata"]["resourceVersion"] = existing["metadata"][
            "resourceVersion"
        ]
        result = api.replace_namespaced_custom_object(
            group=ROLLOUTS_GROUP,
            version=ROLLOUTS_VERSION,
            namespace=namespace,
            plural=ROLLOUTS_PLURAL,
            name=name,
            body=manifest,
        )
        logger.info("Updated Rollout '%s' in %s/%s", name, cluster, namespace)
        return result
    except ApiException as e:
        if e.status == 404:
            result = api.create_namespaced_custom_object(
                group=ROLLOUTS_GROUP,
                version=ROLLOUTS_VERSION,
                namespace=namespace,
                plural=ROLLOUTS_PLURAL,
                body=manifest,
            )
            logger.info("Created Rollout '%s' in %s/%s", name, cluster, namespace)
            return result
        raise


async def get_rollout_status(cluster: str, namespace: str, name: str) -> dict:
    """Fetch a Rollout CR and return a flat status summary."""
    if not await check_rollouts_available(cluster):
        raise RolloutsNotAvailable(
            f"Argo Rollouts CRDs are not installed on cluster '{cluster}'"
        )

    api = _custom_api(cluster)
    try:
        obj = api.get_namespaced_custom_object(
            group=ROLLOUTS_GROUP,
            version=ROLLOUTS_VERSION,
            namespace=namespace,
            plural=ROLLOUTS_PLURAL,
            name=name,
        )
    except ApiException as e:
        if e.status == 404:
            return {
                "phase": "NotFound",
                "currentStepIndex": None,
                "stableRevision": None,
                "canaryRevision": None,
                "activeService": None,
                "previewService": None,
                "message": f"Rollout '{name}' not found",
                "currentStepHash": None,
            }
        raise

    spec = obj.get("spec", {}) or {}
    status = obj.get("status", {}) or {}
    strategy_spec = spec.get("strategy", {}) or {}
    blue_green = strategy_spec.get("blueGreen", {}) or {}

    return {
        "phase": status.get("phase") or "Unknown",
        "currentStepIndex": status.get("currentStepIndex"),
        "stableRevision": status.get("stableRS"),
        "canaryRevision": status.get("currentPodHash"),
        "activeService": blue_green.get("activeService"),
        "previewService": blue_green.get("previewService"),
        "message": status.get("message"),
        "currentStepHash": status.get("currentStepHash"),
    }


async def _patch_rollout(
    cluster: str, namespace: str, name: str, patch: dict
) -> dict:
    if not await check_rollouts_available(cluster):
        raise RolloutsNotAvailable(
            f"Argo Rollouts CRDs are not installed on cluster '{cluster}'"
        )
    api = _custom_api(cluster)
    return api.patch_namespaced_custom_object(
        group=ROLLOUTS_GROUP,
        version=ROLLOUTS_VERSION,
        namespace=namespace,
        plural=ROLLOUTS_PLURAL,
        name=name,
        body=patch,
    )


async def promote_rollout(cluster: str, namespace: str, name: str) -> None:
    """Promote a paused Rollout to its next step / active state.

    This mirrors what `kubectl argo rollouts promote` does: clear the paused
    flag and set the promote annotation that the argo-rollouts controller
    watches for. The controller then advances the rollout and clears the
    annotation on its next reconcile.
    """
    patch = {
        "metadata": {
            "annotations": {
                "rollout.argoproj.io/promote": "true",
            }
        },
        "spec": {"paused": False},
    }
    await _patch_rollout(cluster, namespace, name, patch)
    logger.info("Promoted Rollout '%s' in %s/%s", name, cluster, namespace)


async def abort_rollout(cluster: str, namespace: str, name: str) -> None:
    """Abort a Rollout, rolling back to the stable revision.

    The status.abort field is owned by the argo-rollouts controller and not
    directly writable via the normal CR patch path; instead we set the
    equivalent spec annotation that the controller honors (same mechanic as
    `kubectl argo rollouts abort`).
    """
    patch = {
        "metadata": {
            "annotations": {
                "rollout.argoproj.io/abort": "true",
            }
        },
        "spec": {"paused": True},
    }
    await _patch_rollout(cluster, namespace, name, patch)
    logger.info("Aborted Rollout '%s' in %s/%s", name, cluster, namespace)


async def pause_rollout(cluster: str, namespace: str, name: str) -> None:
    """Pause a Rollout by setting spec.paused=true."""
    patch = {"spec": {"paused": True}}
    await _patch_rollout(cluster, namespace, name, patch)
    logger.info("Paused Rollout '%s' in %s/%s", name, cluster, namespace)
