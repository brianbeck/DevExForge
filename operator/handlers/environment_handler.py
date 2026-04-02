"""Kopf handlers for the Environment custom resource."""

import datetime
import logging
import os

import kopf
from kubernetes.client import (
    V1Namespace,
    V1ObjectMeta,
)
from kubernetes.client.exceptions import ApiException

from helpers import (
    build_appproject,
    build_limit_range,
    build_network_policy,
    build_resource_quota,
    build_role_bindings_for_team,
    get_k8s_clients,
    sanitize_name,
)

logger = logging.getLogger("devexforge.environment")

GROUP = "devexforge.brianbeck.net"
VERSION = "v1alpha1"
PLURAL_TEAMS = "teams"
PLURAL_ENVIRONMENTS = "environments"


@kopf.on.create(GROUP, VERSION, PLURAL_ENVIRONMENTS)
async def environment_create(spec, name, namespace, patch, **_kwargs):
    """Handle Environment creation: full reconciliation of namespace and resources."""
    logger.info("Creating Environment %s", name)

    core_api, rbac_api, custom_api, net_api = get_k8s_clients()

    team_ref = spec.get("teamRef")
    tier = spec.get("tier", "dev")
    namespace_name = sanitize_name(f"{team_ref}-{tier}")
    resources_created = []

    # 1. Validate teamRef exists
    team_spec = _get_team(custom_api, team_ref, namespace)
    if team_spec is None:
        raise kopf.TemporaryError(
            f"Team '{team_ref}' not found. Will retry.",
            delay=30,
        )

    # 2. Create Namespace
    _create_namespace(core_api, namespace_name, team_ref, tier)
    resources_created.append(f"Namespace/{namespace_name}")

    # 3. Create ResourceQuota
    quota_spec = spec.get("resourceQuota")
    _create_resource_quota(core_api, namespace_name, quota_spec)
    resources_created.append(f"ResourceQuota/{namespace_name}/default")

    # 4. Create LimitRange
    lr_spec = spec.get("limitRange")
    _create_limit_range(core_api, namespace_name, lr_spec)
    resources_created.append(f"LimitRange/{namespace_name}/default")

    # 5. Create NetworkPolicy
    netpol_spec = spec.get("networkPolicy")
    ingress_ns = os.environ.get("DEFAULT_INGRESS_NAMESPACE", "traefik")
    _create_network_policy(net_api, namespace_name, netpol_spec, ingress_ns)
    resources_created.append(f"NetworkPolicy/{namespace_name}/default")

    # 6. Create RoleBindings
    members = team_spec.get("members", [])
    _reconcile_role_bindings(rbac_api, namespace_name, members)
    resources_created.append(f"RoleBindings/{namespace_name}")

    # 7. Create Gatekeeper constraints
    policies = spec.get("policies")
    gk_created = _create_gatekeeper_constraints(custom_api, namespace_name, policies)
    resources_created.extend(gk_created)

    # 8. Create Argo CD AppProject if enabled
    argocd_config = spec.get("argoCD", {})
    if argocd_config.get("enabled", False):
        _create_appproject(custom_api, namespace_name, team_spec, spec)
        resources_created.append(f"AppProject/{namespace_name}")

    # 9. Update status
    patch.status["phase"] = "Active"
    patch.status["namespaceName"] = namespace_name
    patch.status["resourcesCreated"] = resources_created
    patch.status["conditions"] = [
        {
            "type": "Ready",
            "status": "True",
            "reason": "EnvironmentReady",
            "message": "All resources created successfully",
            "lastTransitionTime": _now_iso(),
        },
    ]

    logger.info("Environment %s created with namespace %s", name, namespace_name)


@kopf.on.update(GROUP, VERSION, PLURAL_ENVIRONMENTS)
async def environment_update(spec, old, new, diff, name, namespace, patch, **_kwargs):
    """Handle Environment update: selectively reconcile changed resources."""
    logger.info("Updating Environment %s", name)

    core_api, rbac_api, custom_api, net_api = get_k8s_clients()

    team_ref = spec.get("teamRef")
    tier = spec.get("tier", "dev")
    namespace_name = sanitize_name(f"{team_ref}-{tier}")

    team_spec = _get_team(custom_api, team_ref, namespace)
    if team_spec is None:
        raise kopf.TemporaryError(
            f"Team '{team_ref}' not found. Will retry.",
            delay=30,
        )

    changed_fields = {field_path[1] for op, field_path, _, _ in diff if len(field_path) > 1 and field_path[0] == "spec"}

    if "resourceQuota" in changed_fields:
        logger.info("ResourceQuota changed for %s, patching", namespace_name)
        quota = build_resource_quota(namespace_name, spec.get("resourceQuota"))
        try:
            core_api.replace_namespaced_resource_quota(
                name="default",
                namespace=namespace_name,
                body=quota,
            )
        except ApiException as e:
            if e.status == 404:
                core_api.create_namespaced_resource_quota(
                    namespace=namespace_name,
                    body=quota,
                )
            else:
                raise

    if "limitRange" in changed_fields:
        logger.info("LimitRange changed for %s, patching", namespace_name)
        lr = build_limit_range(namespace_name, spec.get("limitRange"))
        try:
            core_api.replace_namespaced_limit_range(
                name="default",
                namespace=namespace_name,
                body=lr,
            )
        except ApiException as e:
            if e.status == 404:
                core_api.create_namespaced_limit_range(
                    namespace=namespace_name,
                    body=lr,
                )
            else:
                raise

    if "networkPolicy" in changed_fields:
        logger.info("NetworkPolicy changed for %s, patching", namespace_name)
        ingress_ns = os.environ.get("DEFAULT_INGRESS_NAMESPACE", "traefik")
        netpol = build_network_policy(namespace_name, spec.get("networkPolicy"), ingress_ns)
        try:
            net_api.replace_namespaced_network_policy(
                name="default",
                namespace=namespace_name,
                body=netpol,
            )
        except ApiException as e:
            if e.status == 404:
                net_api.create_namespaced_network_policy(
                    namespace=namespace_name,
                    body=netpol,
                )
            else:
                raise

    if "policies" in changed_fields:
        logger.info("Policies changed for %s, reconciling Gatekeeper constraints", namespace_name)
        _create_gatekeeper_constraints(custom_api, namespace_name, spec.get("policies"))

    if "argoCD" in changed_fields:
        argocd_config = spec.get("argoCD", {})
        if argocd_config.get("enabled", False):
            logger.info("ArgoCD config changed for %s, reconciling AppProject", namespace_name)
            _create_appproject(custom_api, namespace_name, team_spec, spec)
        else:
            logger.info("ArgoCD disabled for %s, removing AppProject", namespace_name)
            _delete_appproject(custom_api, namespace_name)

    # Always re-reconcile RBAC if triggered by annotation (members changed on Team CR)
    # or if teamRef changed
    if "teamRef" in changed_fields or any(
        "annotations" in str(fp) and "reconcile-trigger" in str(fp)
        for op, fp, _, _ in diff
    ):
        members = team_spec.get("members", [])
        _reconcile_role_bindings(rbac_api, namespace_name, members)

    patch.status["conditions"] = [
        {
            "type": "Ready",
            "status": "True",
            "reason": "EnvironmentUpdated",
            "message": "Environment updated successfully",
            "lastTransitionTime": _now_iso(),
        },
    ]

    logger.info("Environment %s updated", name)


@kopf.on.delete(GROUP, VERSION, PLURAL_ENVIRONMENTS)
async def environment_delete(spec, name, namespace, **_kwargs):
    """Handle Environment deletion: remove all managed resources in reverse order."""
    logger.info("Deleting Environment %s", name)

    core_api, rbac_api, custom_api, net_api = get_k8s_clients()

    team_ref = spec.get("teamRef")
    tier = spec.get("tier", "dev")
    namespace_name = sanitize_name(f"{team_ref}-{tier}")

    # 1. Delete AppProject
    _delete_appproject(custom_api, namespace_name)

    # 2. Delete Gatekeeper constraints (any constraints targeting this namespace)
    _delete_gatekeeper_constraints(custom_api, namespace_name)

    # 3. Delete RoleBindings
    _delete_role_bindings(rbac_api, namespace_name)

    # 4. Delete NetworkPolicy
    _delete_resource(
        lambda: net_api.delete_namespaced_network_policy(
            name="default", namespace=namespace_name
        ),
        "NetworkPolicy",
        namespace_name,
    )

    # 5. Delete LimitRange
    _delete_resource(
        lambda: core_api.delete_namespaced_limit_range(
            name="default", namespace=namespace_name
        ),
        "LimitRange",
        namespace_name,
    )

    # 6. Delete ResourceQuota
    _delete_resource(
        lambda: core_api.delete_namespaced_resource_quota(
            name="default", namespace=namespace_name
        ),
        "ResourceQuota",
        namespace_name,
    )

    # 7. Delete Namespace
    _delete_resource(
        lambda: core_api.delete_namespace(name=namespace_name),
        "Namespace",
        namespace_name,
    )

    logger.info("Environment %s deleted, namespace %s removed", name, namespace_name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_team(custom_api, team_ref: str, namespace: str) -> dict | None:
    """Fetch a Team CR spec. Returns the full spec dict or None if not found."""
    try:
        team = custom_api.get_cluster_custom_object(
            group=GROUP,
            version=VERSION,
            plural=PLURAL_TEAMS,
            name=team_ref,
        )
        return team.get("spec", {})
    except ApiException as e:
        if e.status == 404:
            # Try namespaced lookup as fallback
            try:
                team = custom_api.get_namespaced_custom_object(
                    group=GROUP,
                    version=VERSION,
                    plural=PLURAL_TEAMS,
                    namespace=namespace,
                    name=team_ref,
                )
                return team.get("spec", {})
            except ApiException as e2:
                if e2.status == 404:
                    return None
                raise
        raise


def _create_namespace(core_api, namespace_name: str, team_ref: str, tier: str) -> None:
    """Create a namespace with standard labels."""
    ns = V1Namespace(
        metadata=V1ObjectMeta(
            name=namespace_name,
            labels={
                "devexforge.brianbeck.net/team": team_ref,
                "devexforge.brianbeck.net/tier": tier,
                "devexforge.brianbeck.net/managed-by": "devexforge-operator",
                "admission": "enabled",
            },
        ),
    )
    try:
        core_api.create_namespace(body=ns)
        logger.info("Created namespace %s", namespace_name)
    except ApiException as e:
        if e.status == 409:
            logger.info("Namespace %s already exists, patching labels", namespace_name)
            core_api.patch_namespace(
                name=namespace_name,
                body={
                    "metadata": {
                        "labels": ns.metadata.labels,
                    },
                },
            )
        else:
            raise


def _create_resource_quota(core_api, namespace_name: str, quota_spec: dict | None) -> None:
    """Create a ResourceQuota in the given namespace."""
    quota = build_resource_quota(namespace_name, quota_spec)
    try:
        core_api.create_namespaced_resource_quota(namespace=namespace_name, body=quota)
        logger.info("Created ResourceQuota in %s", namespace_name)
    except ApiException as e:
        if e.status == 409:
            logger.info("ResourceQuota in %s already exists, replacing", namespace_name)
            core_api.replace_namespaced_resource_quota(
                name="default", namespace=namespace_name, body=quota
            )
        else:
            raise


def _create_limit_range(core_api, namespace_name: str, lr_spec: dict | None) -> None:
    """Create a LimitRange in the given namespace."""
    lr = build_limit_range(namespace_name, lr_spec)
    try:
        core_api.create_namespaced_limit_range(namespace=namespace_name, body=lr)
        logger.info("Created LimitRange in %s", namespace_name)
    except ApiException as e:
        if e.status == 409:
            logger.info("LimitRange in %s already exists, replacing", namespace_name)
            core_api.replace_namespaced_limit_range(
                name="default", namespace=namespace_name, body=lr
            )
        else:
            raise


def _create_network_policy(
    net_api, namespace_name: str, netpol_spec: dict | None, ingress_ns: str
) -> None:
    """Create a NetworkPolicy in the given namespace."""
    netpol = build_network_policy(namespace_name, netpol_spec, ingress_ns)
    try:
        net_api.create_namespaced_network_policy(namespace=namespace_name, body=netpol)
        logger.info("Created NetworkPolicy in %s", namespace_name)
    except ApiException as e:
        if e.status == 409:
            logger.info("NetworkPolicy in %s already exists, replacing", namespace_name)
            net_api.replace_namespaced_network_policy(
                name="default", namespace=namespace_name, body=netpol
            )
        else:
            raise


def _reconcile_role_bindings(rbac_api, namespace_name: str, members: list[dict]) -> None:
    """Create or update RoleBindings for team members in the namespace."""
    desired_bindings = build_role_bindings_for_team(namespace_name, members)

    # Delete existing devexforge-managed bindings first
    try:
        existing = rbac_api.list_namespaced_role_binding(
            namespace=namespace_name,
            label_selector="devexforge.brianbeck.net/managed-by=devexforge-operator",
        )
        for binding in existing.items:
            try:
                rbac_api.delete_namespaced_role_binding(
                    name=binding.metadata.name,
                    namespace=namespace_name,
                )
            except ApiException as e:
                if e.status != 404:
                    raise
    except ApiException as e:
        if e.status != 404:
            raise

    # Create new bindings
    for binding in desired_bindings:
        try:
            rbac_api.create_namespaced_role_binding(
                namespace=namespace_name,
                body=binding,
            )
            logger.info(
                "Created RoleBinding %s in %s",
                binding.metadata.name,
                namespace_name,
            )
        except ApiException as e:
            if e.status == 409:
                rbac_api.replace_namespaced_role_binding(
                    name=binding.metadata.name,
                    namespace=namespace_name,
                    body=binding,
                )
                logger.info(
                    "Replaced RoleBinding %s in %s",
                    binding.metadata.name,
                    namespace_name,
                )
            else:
                raise


def _create_appproject(
    custom_api, namespace_name: str, team_spec: dict, env_spec: dict
) -> None:
    """Create or update an Argo CD AppProject."""
    argocd_ns = os.environ.get("ARGOCD_NAMESPACE", "argocd")
    appproject = build_appproject(namespace_name, team_spec, env_spec)
    try:
        custom_api.create_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=argocd_ns,
            plural="appprojects",
            body=appproject,
        )
        logger.info("Created AppProject %s", namespace_name)
    except ApiException as e:
        if e.status == 409:
            custom_api.patch_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=argocd_ns,
                plural="appprojects",
                name=namespace_name,
                body=appproject,
            )
            logger.info("Patched AppProject %s", namespace_name)
        else:
            raise


def _delete_appproject(custom_api, namespace_name: str) -> None:
    """Delete an Argo CD AppProject if it exists."""
    argocd_ns = os.environ.get("ARGOCD_NAMESPACE", "argocd")
    try:
        custom_api.delete_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=argocd_ns,
            plural="appprojects",
            name=namespace_name,
        )
        logger.info("Deleted AppProject %s", namespace_name)
    except ApiException as e:
        if e.status == 404:
            logger.debug("AppProject %s not found, skipping", namespace_name)
        else:
            raise


def _create_gatekeeper_constraints(
    custom_api, namespace_name: str, policies: dict | None
) -> list[str]:
    """Create Gatekeeper constraint instances scoped to the given namespace.

    Uses existing constraint templates:
    - FalcoRootPrevention (from secops/constraint-template.yaml)
    - VulnerabilityScan (from capoc/cve/cve-constraint-template.yaml)

    Returns list of created resource names for status tracking.
    """
    if policies is None:
        policies = {}

    created = []
    exemptions = policies.get("exemptions", {})
    exempt_images = exemptions.get("exemptImages", [])

    # 1. FalcoRootPrevention constraint (if requireNonRoot is true)
    if policies.get("requireNonRoot", True):
        constraint_name = f"{namespace_name}-no-root"
        body = {
            "apiVersion": "constraints.gatekeeper.sh/v1beta1",
            "kind": "FalcoRootPrevention",
            "metadata": {
                "name": constraint_name,
                "labels": {
                    "devexforge.brianbeck.net/managed-by": "devexforge-operator",
                    "devexforge.brianbeck.net/environment": namespace_name,
                },
            },
            "spec": {
                "match": {
                    "kinds": [
                        {"apiGroups": ["apps"], "kinds": ["Deployment"]},
                        {"apiGroups": [""], "kinds": ["Pod"]},
                    ],
                    "namespaces": [namespace_name],
                },
                "parameters": {
                    "exemptImages": exempt_images,
                    "exemptNamespaces": exemptions.get("exemptNamespaces", []),
                },
            },
        }
        _apply_gatekeeper_constraint(custom_api, "falcorootprevention", constraint_name, body)
        created.append(f"FalcoRootPrevention/{constraint_name}")
    else:
        # Clean up if it exists but is no longer required
        _delete_gatekeeper_constraint(custom_api, "falcorootprevention", f"{namespace_name}-no-root")

    # 2. VulnerabilityScan constraint
    max_critical = policies.get("maxCriticalCVEs", 0)
    max_high = policies.get("maxHighCVEs", 5)
    constraint_name = f"{namespace_name}-vuln-scan"
    body = {
        "apiVersion": "constraints.gatekeeper.sh/v1beta1",
        "kind": "VulnerabilityScan",
        "metadata": {
            "name": constraint_name,
            "labels": {
                "devexforge.brianbeck.net/managed-by": "devexforge-operator",
                "devexforge.brianbeck.net/environment": namespace_name,
            },
        },
        "spec": {
            "match": {
                "kinds": [
                    {"apiGroups": ["apps"], "kinds": ["Deployment"]},
                ],
                "namespaces": [namespace_name],
            },
            "parameters": {
                "maxCriticalCVEs": max_critical,
                "maxHighCVEs": max_high,
                "allowedImages": exempt_images,
                "vulnerabilityData": {},
            },
        },
    }
    _apply_gatekeeper_constraint(custom_api, "vulnerabilityscan", constraint_name, body)
    created.append(f"VulnerabilityScan/{constraint_name}")

    return created


def _apply_gatekeeper_constraint(custom_api, plural: str, name: str, body: dict) -> None:
    """Create or update a Gatekeeper constraint."""
    try:
        existing = custom_api.get_cluster_custom_object(
            group="constraints.gatekeeper.sh",
            version="v1beta1",
            plural=plural,
            name=name,
        )
        body["metadata"]["resourceVersion"] = existing["metadata"]["resourceVersion"]
        custom_api.replace_cluster_custom_object(
            group="constraints.gatekeeper.sh",
            version="v1beta1",
            plural=plural,
            name=name,
            body=body,
        )
        logger.info("Updated Gatekeeper constraint %s/%s", plural, name)
    except ApiException as e:
        if e.status == 404:
            custom_api.create_cluster_custom_object(
                group="constraints.gatekeeper.sh",
                version="v1beta1",
                plural=plural,
                body=body,
            )
            logger.info("Created Gatekeeper constraint %s/%s", plural, name)
        else:
            raise


def _delete_gatekeeper_constraint(custom_api, plural: str, name: str) -> None:
    """Delete a Gatekeeper constraint if it exists."""
    try:
        custom_api.delete_cluster_custom_object(
            group="constraints.gatekeeper.sh",
            version="v1beta1",
            plural=plural,
            name=name,
        )
        logger.info("Deleted Gatekeeper constraint %s/%s", plural, name)
    except ApiException as e:
        if e.status == 404:
            logger.debug("Gatekeeper constraint %s/%s not found, skipping", plural, name)
        else:
            raise


def _delete_gatekeeper_constraints(custom_api, namespace_name: str) -> None:
    """Delete Gatekeeper constraints that reference this namespace."""
    # Delete our specific Gatekeeper constraints
    _delete_gatekeeper_constraint(custom_api, "falcorootprevention", f"{namespace_name}-no-root")
    _delete_gatekeeper_constraint(custom_api, "vulnerabilityscan", f"{namespace_name}-vuln-scan")


def _delete_role_bindings(rbac_api, namespace_name: str) -> None:
    """Delete all devexforge-managed RoleBindings in the namespace."""
    try:
        bindings = rbac_api.list_namespaced_role_binding(
            namespace=namespace_name,
            label_selector="devexforge.brianbeck.net/managed-by=devexforge-operator",
        )
        for binding in bindings.items:
            try:
                rbac_api.delete_namespaced_role_binding(
                    name=binding.metadata.name,
                    namespace=namespace_name,
                )
                logger.info("Deleted RoleBinding %s in %s", binding.metadata.name, namespace_name)
            except ApiException as e:
                if e.status != 404:
                    raise
    except ApiException as e:
        if e.status == 404:
            logger.debug("No RoleBindings found in %s", namespace_name)
        else:
            raise


def _delete_resource(delete_fn, resource_type: str, identifier: str) -> None:
    """Generic delete wrapper that handles NotFound gracefully."""
    try:
        delete_fn()
        logger.info("Deleted %s %s", resource_type, identifier)
    except ApiException as e:
        if e.status == 404:
            logger.debug("%s %s not found, skipping", resource_type, identifier)
        else:
            raise


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
