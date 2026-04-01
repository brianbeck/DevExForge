import logging

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from app.config import settings
from app.models.environment import Environment
from app.models.team import Team, TeamMember

logger = logging.getLogger(__name__)


class K8sService:
    """Multi-cluster Kubernetes service. Manages CRDs across stage and prod clusters."""

    def __init__(self) -> None:
        self._group = settings.K8S_CRD_GROUP
        self._version = settings.K8S_CRD_VERSION
        self._clients: dict[str, client.CustomObjectsApi] = {}

        if settings.K8S_IN_CLUSTER:
            # When running in-cluster (prod), load in-cluster config for prod
            config.load_incluster_config()
            self._clients["beck-prod"] = client.CustomObjectsApi()
            # For stage cluster, load from kubeconfig with specific context
            try:
                stage_api_client = config.new_client_from_config(
                    context=settings.K8S_STAGE_CONTEXT
                )
                self._clients["beck-stage"] = client.CustomObjectsApi(api_client=stage_api_client)
            except Exception:
                logger.warning("Could not load stage cluster config; stage operations will fail")
        else:
            # Local development: load both contexts from kubeconfig
            try:
                prod_api_client = config.new_client_from_config(
                    context=settings.K8S_PROD_CONTEXT
                )
                self._clients["beck-prod"] = client.CustomObjectsApi(api_client=prod_api_client)
            except Exception:
                logger.warning("Could not load prod cluster config")
            try:
                stage_api_client = config.new_client_from_config(
                    context=settings.K8S_STAGE_CONTEXT
                )
                self._clients["beck-stage"] = client.CustomObjectsApi(api_client=stage_api_client)
            except Exception:
                logger.warning("Could not load stage cluster config")

    def _get_api(self, cluster: str) -> client.CustomObjectsApi:
        """Get the CustomObjectsApi for the specified cluster."""
        api = self._clients.get(cluster)
        if api is None:
            raise RuntimeError(f"No Kubernetes client configured for cluster '{cluster}'")
        return api

    def cluster_for_tier(self, tier: str) -> str:
        """Map a tier to its target cluster name."""
        cluster = settings.TIER_CLUSTER_MAP.get(tier)
        if cluster is None:
            raise ValueError(f"No cluster mapping for tier '{tier}'")
        return cluster

    def apply_team_crd(self, team: Team, members: list[TeamMember]) -> dict:
        """Apply Team CRD to BOTH clusters (teams are global)."""
        body = {
            "apiVersion": f"{self._group}/{self._version}",
            "kind": "Team",
            "metadata": {"name": team.slug},
            "spec": {
                "displayName": team.display_name,
                "description": team.description or "",
                "owner": {
                    "email": team.owner_email,
                    "keycloakId": team.owner_keycloak_id or "",
                },
                "costCenter": team.cost_center or "",
                "tags": team.tags or {},
                "members": [
                    {"email": m.email, "role": m.role, "keycloakId": m.keycloak_id or ""}
                    for m in members
                ],
            },
        }

        result = None
        for cluster_name, api in self._clients.items():
            result = self._apply_cluster_crd(api, "teams", team.slug, body, cluster_name)
        return result or {}

    def delete_team_crd(self, slug: str) -> None:
        """Delete Team CRD from BOTH clusters."""
        for cluster_name, api in self._clients.items():
            self._delete_cluster_crd(api, "teams", slug, cluster_name)

    def apply_environment_crd(self, team_slug: str, environment: Environment) -> dict:
        """Apply Environment CRD to the appropriate cluster based on tier."""
        cluster = self.cluster_for_tier(environment.tier)
        api = self._get_api(cluster)
        name = f"{team_slug}-{environment.tier}"

        body = {
            "apiVersion": f"{self._group}/{self._version}",
            "kind": "Environment",
            "metadata": {"name": name},
            "spec": {
                "teamRef": team_slug,
                "tier": environment.tier,
                "cluster": cluster,
                "namespaceName": environment.namespace_name,
                "resourceQuota": environment.resource_quota or {},
                "limitRange": environment.limit_range or {},
                "networkPolicy": environment.network_policy or {},
                "policies": environment.policies or {},
                "argoCD": environment.argocd_config or {},
            },
        }

        return self._apply_cluster_crd(api, "environments", name, body, cluster)

    def delete_environment_crd(self, team_slug: str, tier: str) -> None:
        """Delete Environment CRD from the appropriate cluster."""
        cluster = self.cluster_for_tier(tier)
        api = self._get_api(cluster)
        name = f"{team_slug}-{tier}"
        self._delete_cluster_crd(api, "environments", name, cluster)

    def get_argo_application(self, cluster: str, namespace: str, app_name: str) -> dict | None:
        """Read an Argo CD Application CR from the specified cluster."""
        api = self._get_api(cluster)
        try:
            return api.get_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="applications",
                name=app_name,
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def create_argo_application(self, cluster: str, namespace: str, body: dict) -> dict:
        """Create or update an Argo CD Application CR in the specified cluster."""
        api = self._get_api(cluster)
        app_name = body["metadata"]["name"]
        try:
            existing = api.get_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="applications",
                name=app_name,
            )
            body["metadata"]["resourceVersion"] = existing["metadata"]["resourceVersion"]
            return api.replace_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="applications",
                name=app_name,
                body=body,
            )
        except ApiException as e:
            if e.status == 404:
                return api.create_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="applications",
                    body=body,
                )
            raise

    def _apply_cluster_crd(self, api, plural: str, name: str, body: dict, cluster: str) -> dict:
        """Create-or-update a cluster-scoped custom resource."""
        try:
            existing = api.get_cluster_custom_object(
                group=self._group, version=self._version, plural=plural, name=name,
            )
            body["metadata"]["resourceVersion"] = existing["metadata"]["resourceVersion"]
            result = api.replace_cluster_custom_object(
                group=self._group, version=self._version, plural=plural, name=name, body=body,
            )
            logger.info("Updated %s CRD '%s' in %s", plural, name, cluster)
            return result
        except ApiException as e:
            if e.status == 404:
                result = api.create_cluster_custom_object(
                    group=self._group, version=self._version, plural=plural, body=body,
                )
                logger.info("Created %s CRD '%s' in %s", plural, name, cluster)
                return result
            raise

    def _delete_cluster_crd(self, api, plural: str, name: str, cluster: str) -> None:
        """Delete a cluster-scoped custom resource."""
        try:
            api.delete_cluster_custom_object(
                group=self._group, version=self._version, plural=plural, name=name,
            )
            logger.info("Deleted %s CRD '%s' in %s", plural, name, cluster)
        except ApiException as e:
            if e.status == 404:
                logger.info("%s CRD '%s' already deleted in %s", plural, name, cluster)
            else:
                raise


k8s_service = K8sService()
