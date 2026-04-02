"""Helper functions for the DevExForge operator."""

import os
import re
from typing import Any

from kubernetes import client, config
from kubernetes.client import (
    CoreV1Api,
    CustomObjectsApi,
    NetworkingV1Api,
    RbacAuthorizationV1Api,
    V1LimitRange,
    V1LimitRangeItem,
    V1LimitRangeSpec,
    V1ObjectMeta,
    V1ResourceQuota,
    V1ResourceQuotaSpec,
    V1RoleBinding,
    V1RoleRef,
    RbacV1Subject,
)

_clients_initialized = False


def _ensure_kube_config():
    global _clients_initialized
    if not _clients_initialized:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        _clients_initialized = True


def get_k8s_clients() -> tuple[CoreV1Api, RbacAuthorizationV1Api, CustomObjectsApi, NetworkingV1Api]:
    """Return initialized Kubernetes API clients."""
    _ensure_kube_config()
    return (
        CoreV1Api(),
        RbacAuthorizationV1Api(),
        CustomObjectsApi(),
        NetworkingV1Api(),
    )


def sanitize_name(name: str) -> str:
    """Convert a string to a valid Kubernetes resource name.

    Lowercase, replace non-alphanumeric chars with hyphens, strip leading/trailing
    hyphens, and truncate to 63 characters.
    """
    name = name.lower()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name[:63]


DEFAULT_QUOTA = {
    "requests.cpu": "4",
    "requests.memory": "8Gi",
    "limits.cpu": "8",
    "limits.memory": "16Gi",
    "persistentvolumeclaims": "10",
    "services": "20",
    "pods": "50",
}

DEFAULT_LIMIT_RANGE_CONTAINER = {
    "default": {"cpu": "500m", "memory": "512Mi"},
    "defaultRequest": {"cpu": "100m", "memory": "128Mi"},
    "max": {"cpu": "2", "memory": "4Gi"},
    "min": {"cpu": "50m", "memory": "64Mi"},
}


CRD_TO_QUOTA_KEY = {
    "cpuRequest": "requests.cpu",
    "cpuLimit": "limits.cpu",
    "memoryRequest": "requests.memory",
    "memoryLimit": "limits.memory",
    "pods": "pods",
    "services": "services",
    "persistentVolumeClaims": "persistentvolumeclaims",
}


def build_resource_quota(
    namespace: str,
    spec: dict[str, Any] | None,
) -> V1ResourceQuota:
    """Build a V1ResourceQuota from a spec dict, applying defaults."""
    hard = dict(DEFAULT_QUOTA)
    if spec:
        for crd_key, value in spec.items():
            k8s_key = CRD_TO_QUOTA_KEY.get(crd_key, crd_key)
            hard[k8s_key] = str(value)

    return V1ResourceQuota(
        metadata=V1ObjectMeta(
            name="default",
            namespace=namespace,
            labels={
                "devexforge.brianbeck.net/managed-by": "devexforge-operator",
            },
        ),
        spec=V1ResourceQuotaSpec(hard=hard),
    )


def build_limit_range(
    namespace: str,
    spec: dict[str, Any] | None,
) -> V1LimitRange:
    """Build a V1LimitRange from a spec dict, applying defaults."""
    container_limits = dict(DEFAULT_LIMIT_RANGE_CONTAINER)
    if spec:
        # Map CRD flat fields to nested K8s LimitRange structure
        if "defaultCpuLimit" in spec or "defaultMemoryLimit" in spec:
            container_limits["default"] = {
                "cpu": spec.get("defaultCpuLimit", container_limits["default"]["cpu"]),
                "memory": spec.get("defaultMemoryLimit", container_limits["default"]["memory"]),
            }
        if "defaultCpuRequest" in spec or "defaultMemoryRequest" in spec:
            container_limits["defaultRequest"] = {
                "cpu": spec.get("defaultCpuRequest", container_limits["defaultRequest"]["cpu"]),
                "memory": spec.get("defaultMemoryRequest", container_limits["defaultRequest"]["memory"]),
            }
        # Also accept already-nested format
        for key in ("default", "defaultRequest", "max", "min"):
            if key in spec and isinstance(spec[key], dict):
                container_limits[key] = spec[key]

    return V1LimitRange(
        metadata=V1ObjectMeta(
            name="default",
            namespace=namespace,
            labels={
                "devexforge.brianbeck.net/managed-by": "devexforge-operator",
            },
        ),
        spec=V1LimitRangeSpec(
            limits=[
                V1LimitRangeItem(
                    type="Container",
                    default=container_limits["default"],
                    default_request=container_limits["defaultRequest"],
                    max=container_limits["max"],
                    min=container_limits["min"],
                ),
            ],
        ),
    )


def build_network_policy(
    namespace: str,
    spec: dict[str, Any] | None,
    ingress_namespace: str | None = None,
) -> dict[str, Any]:
    """Build a NetworkPolicy manifest dict."""
    if ingress_namespace is None:
        ingress_namespace = os.environ.get("DEFAULT_INGRESS_NAMESPACE", "traefik")

    ingress_rules: list[dict[str, Any]] = [
        # Allow from same namespace
        {
            "from": [
                {
                    "podSelector": {},
                },
            ],
        },
        # Allow from ingress namespace
        {
            "from": [
                {
                    "namespaceSelector": {
                        "matchLabels": {
                            "kubernetes.io/metadata.name": ingress_namespace,
                        },
                    },
                },
            ],
        },
    ]

    # Allow inter-namespace traffic if configured
    if spec and spec.get("allowInterNamespace"):
        allowed_namespaces = spec.get("allowedNamespaces", [])
        for ns in allowed_namespaces:
            ingress_rules.append(
                {
                    "from": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {
                                    "kubernetes.io/metadata.name": ns,
                                },
                            },
                        },
                    ],
                }
            )

    egress_rules: list[dict[str, Any]] = [
        # Always allow DNS
        {
            "to": [],
            "ports": [
                {"protocol": "UDP", "port": 53},
                {"protocol": "TCP", "port": 53},
            ],
        },
    ]

    # Optionally allow all internet egress
    if spec and spec.get("egressAllowInternet", True):
        egress_rules.append({})

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": "default",
            "namespace": namespace,
            "labels": {
                "devexforge.brianbeck.net/managed-by": "devexforge-operator",
            },
        },
        "spec": {
            "podSelector": {},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": ingress_rules,
            "egress": egress_rules,
        },
    }


def _cluster_role_for_member_role(role: str) -> str:
    """Map a team member role to a ClusterRole name."""
    if role in ("owner", "admin"):
        return "admin"
    if role == "developer":
        return "edit"
    return "view"


def build_role_binding(
    namespace: str,
    name: str,
    cluster_role: str,
    subjects: list[dict[str, str]],
) -> V1RoleBinding:
    """Build a V1RoleBinding."""
    return V1RoleBinding(
        metadata=V1ObjectMeta(
            name=name,
            namespace=namespace,
            labels={
                "devexforge.brianbeck.net/managed-by": "devexforge-operator",
            },
        ),
        role_ref=V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name=cluster_role,
        ),
        subjects=[
            RbacV1Subject(
                kind="User",
                name=subj["email"],
                api_group="rbac.authorization.k8s.io",
            )
            for subj in subjects
        ],
    )


def build_role_bindings_for_team(
    namespace: str,
    members: list[dict[str, Any]],
) -> list[V1RoleBinding]:
    """Build RoleBindings for all team members grouped by effective ClusterRole."""
    by_cluster_role: dict[str, list[dict[str, str]]] = {}
    for member in members:
        role = member.get("role", "viewer")
        cr = _cluster_role_for_member_role(role)
        by_cluster_role.setdefault(cr, []).append(member)

    bindings = []
    for cr, subjects in by_cluster_role.items():
        binding_name = f"devexforge-{cr}"
        bindings.append(build_role_binding(namespace, binding_name, cr, subjects))
    return bindings


def build_appproject(
    namespace_name: str,
    team_spec: dict[str, Any],
    env_spec: dict[str, Any],
) -> dict[str, Any]:
    """Build an Argo CD AppProject manifest dict."""
    argocd_ns = os.environ.get("ARGOCD_NAMESPACE", "argocd")
    argocd_config = env_spec.get("argoCD", {})
    source_repos = argocd_config.get("sourceRepos", ["*"])
    team_name = team_spec.get("displayName", "unknown")
    members = team_spec.get("members", [])

    # Build roles with policies
    admin_policies = [
        f"p, proj:{namespace_name}:admin, applications, *, {namespace_name}/*, allow",
        f"p, proj:{namespace_name}:admin, repositories, *, {namespace_name}/*, allow",
    ]
    dev_policies = [
        f"p, proj:{namespace_name}:developer, applications, get, {namespace_name}/*, allow",
        f"p, proj:{namespace_name}:developer, applications, sync, {namespace_name}/*, allow",
        f"p, proj:{namespace_name}:developer, applications, create, {namespace_name}/*, allow",
        f"p, proj:{namespace_name}:developer, applications, update, {namespace_name}/*, allow",
    ]

    admin_groups = [
        m["email"] for m in members if m.get("role") in ("owner", "admin")
    ]
    dev_groups = [
        m["email"] for m in members if m.get("role") == "developer"
    ]

    roles = []
    if admin_groups:
        roles.append(
            {
                "name": "admin",
                "description": f"Admin role for {team_name}",
                "policies": admin_policies,
                "groups": admin_groups,
            }
        )
    if dev_groups:
        roles.append(
            {
                "name": "developer",
                "description": f"Developer role for {team_name}",
                "policies": dev_policies,
                "groups": dev_groups,
            }
        )

    # Map CRD allowedClusterResources to AppProject clusterResourceWhitelist
    allowed_cluster_resources = argocd_config.get("allowedClusterResources", [])
    cluster_resource_whitelist = [
        {"group": r.get("group", ""), "kind": r.get("kind", "")}
        for r in allowed_cluster_resources
    ]

    project_spec = {
        "description": f"AppProject for environment {namespace_name} (team: {team_name})",
        "sourceRepos": source_repos,
        "destinations": [
            {
                "server": "https://kubernetes.default.svc",
                "namespace": namespace_name,
            },
        ],
        "roles": roles,
    }

    if cluster_resource_whitelist:
        project_spec["clusterResourceWhitelist"] = cluster_resource_whitelist

    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {
            "name": namespace_name,
            "namespace": argocd_ns,
            "labels": {
                "devexforge.brianbeck.net/managed-by": "devexforge-operator",
                "devexforge.brianbeck.net/environment": namespace_name,
            },
        },
        "spec": project_spec,
    }
