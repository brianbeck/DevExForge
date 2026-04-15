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
            self._init_in_cluster()
        else:
            self._init_local()

    def _init_in_cluster(self) -> None:
        """Initialize clients when running inside a Kubernetes cluster."""
        config.load_incluster_config()
        in_cluster_api = client.CustomObjectsApi()

        # Register the in-cluster client for all tiers that map to this cluster
        # In prod: registers as beck-prod. In stage: registers as beck-stage.
        local_clusters = set(settings.TIER_CLUSTER_MAP.values())
        for cluster_name in local_clusters:
            self._clients[cluster_name] = in_cluster_api

        # If a remote cluster context is configured, load it
        self._load_context(settings.K8S_STAGE_CONTEXT, "beck-stage")
        self._load_context(settings.K8S_PROD_CONTEXT, "beck-prod")

    def _init_local(self) -> None:
        """Initialize clients for local development from kubeconfig."""
        self._load_context(settings.K8S_PROD_CONTEXT, "beck-prod")
        self._load_context(settings.K8S_STAGE_CONTEXT, "beck-stage")

    def _load_context(self, context_name: str | None, cluster_name: str) -> None:
        """Load a kubeconfig context and register the client for a cluster."""
        if not context_name:
            return
        try:
            api_client = config.new_client_from_config(context=context_name)
            self._clients[cluster_name] = client.CustomObjectsApi(api_client=api_client)
        except Exception:
            logger.warning("Could not load %s cluster config; %s operations will fail", cluster_name, cluster_name)

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

    def list_argo_applications(
        self,
        cluster: str,
        namespace: str = "argocd",
        label_selector: str | None = None,
    ) -> list[dict]:
        """List Argo CD Application CRs in the specified cluster/namespace.

        Optionally filter by label selector (e.g., 'devexforge.brianbeck.net/managed-by=devexforge').
        Returns list of Application CR dicts.
        """
        api = self._get_api(cluster)
        try:
            kwargs = {
                "group": "argoproj.io",
                "version": "v1alpha1",
                "namespace": namespace,
                "plural": "applications",
            }
            if label_selector:
                kwargs["label_selector"] = label_selector
            result = api.list_namespaced_custom_object(**kwargs)
            return result.get("items", [])
        except ApiException as e:
            if e.status == 404:
                return []
            raise

    def sync_argo_application_to_revision(
        self,
        cluster: str,
        namespace: str,
        app_name: str,
        revision: str,
    ) -> dict:
        """Trigger Argo CD to sync an Application to a specific revision.

        Patches the Application CR's `operation` field, which Argo CD's
        application controller picks up and executes. This is the canonical
        rollback mechanism — equivalent to `argocd app sync <name> --revision <rev>`.
        """
        api = self._get_api(cluster)
        patch = {
            "operation": {
                "sync": {
                    "revision": revision,
                    "prune": True,
                    "syncStrategy": {"apply": {"force": False}},
                },
                "initiatedBy": {"username": "devexforge", "automated": True},
            }
        }
        try:
            result = api.patch_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="applications",
                name=app_name,
                body=patch,
            )
            logger.info(
                "Triggered sync of Argo CD Application '%s' to revision %s in %s/%s",
                app_name, revision, cluster, namespace,
            )
            return result
        except ApiException as e:
            logger.error(
                "Failed to sync Application '%s' to revision %s: %s",
                app_name, revision, e,
            )
            raise

    def delete_argo_application(
        self,
        cluster: str,
        namespace: str,
        app_name: str,
    ) -> None:
        """Delete an Argo CD Application CR. Safe if the app doesn't exist."""
        api = self._get_api(cluster)
        try:
            api.delete_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace,
                plural="applications",
                name=app_name,
            )
            logger.info("Deleted Argo CD Application '%s' in %s/%s", app_name, cluster, namespace)
        except ApiException as e:
            if e.status == 404:
                logger.info("Argo CD Application '%s' already deleted in %s", app_name, cluster)
            else:
                raise

    def get_argo_application_health(
        self,
        cluster: str,
        namespace: str,
        app_name: str,
    ) -> dict | None:
        """Return a normalized health summary for an Argo CD Application.

        Returns None if the Application doesn't exist.
        Returns dict with keys:
          health_status: str  (from status.health.status, e.g. 'Healthy', 'Degraded', 'Progressing')
          sync_status:   str  (from status.sync.status, e.g. 'Synced', 'OutOfSync', 'Unknown')
          revision:      str  (from status.sync.revision)
          target_revision: str (from spec.source.targetRevision)
          source_repo:   str  (from spec.source.repoURL)
          image_tag:     str | None  (parsed from status.summary.images if present)
          last_sync_at:  str | None  (from status.operationState.finishedAt if present)
          raw:           dict (full Application CR)
        """
        app = self.get_argo_application(cluster, namespace, app_name)
        if app is None:
            return None

        status = app.get("status", {}) or {}
        spec = app.get("spec", {}) or {}
        health = status.get("health", {}) or {}
        sync = status.get("sync", {}) or {}
        summary = status.get("summary", {}) or {}
        op_state = status.get("operationState", {}) or {}
        source = spec.get("source", {}) or {}

        # Try to extract primary image tag from summary.images (format: "repo/image:tag")
        image_tag: str | None = None
        images = summary.get("images", [])
        if images:
            first = images[0]
            if ":" in first:
                image_tag = first.rsplit(":", 1)[-1]

        return {
            "health_status": health.get("status") or "Unknown",
            "sync_status": sync.get("status") or "Unknown",
            "revision": sync.get("revision") or "",
            "target_revision": source.get("targetRevision") or "",
            "source_repo": source.get("repoURL") or "",
            "image_tag": image_tag,
            "last_sync_at": op_state.get("finishedAt"),
            "raw": app,
        }

    def _get_core_api(self, cluster: str) -> client.CoreV1Api:
        """Get CoreV1Api for the specified cluster."""
        # Reuse the api_client from the CustomObjectsApi
        custom_api = self._get_api(cluster)
        return client.CoreV1Api(api_client=custom_api.api_client)

    def get_resource_quota_usage(self, cluster: str, namespace: str) -> dict:
        """Get resource quota status for a namespace."""
        core = self._get_core_api(cluster)
        try:
            quotas = core.list_namespaced_resource_quota(namespace=namespace)
            if not quotas.items:
                return {"quotas": []}
            result = []
            for q in quotas.items:
                status = q.status
                result.append({
                    "name": q.metadata.name,
                    "hard": status.hard if status and status.hard else {},
                    "used": status.used if status and status.used else {},
                })
            return {"quotas": result}
        except ApiException as e:
            if e.status == 404:
                return {"quotas": []}
            raise

    def list_gatekeeper_violations(self, cluster: str, namespace: str) -> list[dict]:
        """List Gatekeeper constraint violations for a namespace."""
        api = self._get_api(cluster)
        violations = []
        # Check our known constraint types
        for plural in ("falcorootprevention", "vulnerabilityscan"):
            try:
                constraints = api.list_cluster_custom_object(
                    group="constraints.gatekeeper.sh",
                    version="v1beta1",
                    plural=plural,
                )
                for c in constraints.get("items", []):
                    # Filter to constraints scoped to this namespace
                    match_ns = (
                        c.get("spec", {})
                        .get("match", {})
                        .get("namespaces", [])
                    )
                    if namespace not in match_ns:
                        continue
                    # Extract violations from status.violations
                    for v in c.get("status", {}).get("violations", []):
                        violations.append({
                            "constraintKind": c["kind"],
                            "constraintName": c["metadata"]["name"],
                            "message": v.get("message", ""),
                            "enforcementAction": v.get("enforcementAction", "deny"),
                            "resource": {
                                "kind": v.get("kind", ""),
                                "namespace": v.get("namespace", ""),
                                "name": v.get("name", ""),
                            },
                        })
            except ApiException as e:
                if e.status != 404:
                    logger.warning("Failed to list %s constraints: %s", plural, e.reason)
        return violations

    def list_vulnerability_reports(self, cluster: str, namespace: str) -> list[dict]:
        """List Trivy VulnerabilityReport CRs in a namespace."""
        api = self._get_api(cluster)
        try:
            reports = api.list_namespaced_custom_object(
                group="aquasecurity.github.io",
                version="v1alpha1",
                namespace=namespace,
                plural="vulnerabilityreports",
            )
            results = []
            for r in reports.get("items", []):
                report = r.get("report", {})
                summary = report.get("summary", {})
                results.append({
                    "name": r["metadata"]["name"],
                    "image": r.get("metadata", {}).get("labels", {}).get(
                        "trivy-operator.resource.name", ""
                    ),
                    "critical": summary.get("criticalCount", 0),
                    "high": summary.get("highCount", 0),
                    "medium": summary.get("mediumCount", 0),
                    "low": summary.get("lowCount", 0),
                    "scanner": report.get("scanner", {}).get("name", "Trivy"),
                    "updatedAt": report.get("updateTimestamp", ""),
                })
            return results
        except ApiException as e:
            if e.status == 404:
                return []
            raise

    def list_falco_events(self, cluster: str, namespace: str, limit: int = 50) -> list[dict]:
        """List recent Falco events for a namespace by reading Events of type 'FalcoAlert'."""
        core = self._get_core_api(cluster)
        try:
            events = core.list_namespaced_event(
                namespace=namespace,
                field_selector="reason=FalcoAlert",
                limit=limit,
            )
            results = []
            for e in events.items:
                results.append({
                    "timestamp": e.last_timestamp.isoformat() if e.last_timestamp else "",
                    "message": e.message or "",
                    "severity": e.type or "Warning",
                    "source": e.source.component if e.source else "falco",
                    "involvedObject": {
                        "kind": e.involved_object.kind if e.involved_object else "",
                        "name": e.involved_object.name if e.involved_object else "",
                    },
                    "count": e.count or 1,
                })
            return results
        except ApiException as e:
            if e.status == 404:
                return []
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
