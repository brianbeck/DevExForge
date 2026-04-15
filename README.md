# DevExForge

Developer Experience platform for Kubernetes: self-service team and namespace management with policy enforcement, built on FastAPI, React, and Kopf.

Built on top of PlatformForge, which provides the underlying Kubernetes clusters with Traefik, Argo CD, Gatekeeper, Falco, Trivy, and observability stack.

## Architecture

```
Portal/CLI -> API (PostgreSQL) -> Syncs CRDs to cluster -> Operator watches CRDs -> Reconciles K8s resources
```

**Components:**
- **API** (`api/`): FastAPI + PostgreSQL + Alembic, Keycloak JWT auth, tiered policy floors, multi-cluster CRD sync, application inventory, and gated promotion requests
- The API maintains an application inventory (logical app + per-tier deployments) and gates promotions through a pluggable rule registry (platform-mandatory + team-defined). Blue-green and canary rollouts are driven via Argo Rollouts on the target cluster.
- **Portal** (`portal/`): Vite + React + TypeScript with Keycloak auth
- **Operator** (`operator/`): Kopf-based K8s operator that reconciles Team/Environment CRDs into namespaces, quotas, RBAC, NetworkPolicies, Gatekeeper constraints, and Argo CD AppProjects
- **CLI** (`cli/`): Python CLI with Click and Rich for team/environment self-service
- **Keycloak**: Identity provider with realm, client, and user management
- **CRDs** (`crds/`): Team and Environment custom resource definitions (`devexforge.brianbeck.net/v1alpha1`)
- **Helm Chart** (`deploy/helm/devexforge/`): Full deployment chart for all components including Keycloak

## Deployed Endpoints

Configure your domain via the deploy repo values files. The default naming convention:

### Stage

| Service | URL Pattern |
|---------|-------------|
| API | `https://devexforge-api-stage.<domain>` |
| Portal | `https://devexforge-stage.<domain>` |
| Keycloak | `https://keycloak-stage.<domain>` |
| Argo CD | `https://argocd-stage.<domain>` |

### Production

| Service | URL Pattern |
|---------|-------------|
| API | `https://devexforge-api.<domain>` |
| Portal | `https://devexforge.<domain>` |
| Keycloak | `https://keycloak.<domain>` |
| Argo CD | `https://argocd-prod.<domain>` |

## API Endpoints

| Method | Path | Description | Required Role |
|--------|------|-------------|---------------|
| `GET` | `/health` | Liveness check | none |
| `GET` | `/ready` | Readiness (DB check) | none |
| `POST` | `/api/v1/teams` | Create team | `team-leader` |
| `GET` | `/api/v1/teams` | List teams | authenticated |
| `GET` | `/api/v1/teams/{slug}` | Get team | team member |
| `PATCH` | `/api/v1/teams/{slug}` | Update team | team admin |
| `DELETE` | `/api/v1/teams/{slug}` | Delete team | team owner / platform admin |
| `POST` | `/api/v1/teams/{slug}/members` | Add member | team admin |
| `GET` | `/api/v1/teams/{slug}/members` | List members | team member |
| `PATCH` | `/api/v1/teams/{slug}/members/{email}` | Change role | team admin |
| `DELETE` | `/api/v1/teams/{slug}/members/{email}` | Remove member | team admin |
| `POST` | `/api/v1/teams/{slug}/environments` | Create environment | team admin/developer |
| `GET` | `/api/v1/teams/{slug}/environments` | List environments | team member |
| `GET` | `/api/v1/teams/{slug}/environments/{tier}` | Get environment | team member |
| `PATCH` | `/api/v1/teams/{slug}/environments/{tier}` | Update environment | team admin/developer |
| `DELETE` | `/api/v1/teams/{slug}/environments/{tier}` | Delete environment | team admin/developer |
| `GET` | `.../environments/{tier}/violations` | Gatekeeper violations | team member |
| `GET` | `.../environments/{tier}/vulnerabilities` | Trivy scan results | team member |
| `GET` | `.../environments/{tier}/security-events` | Falco alerts | team member |
| `GET` | `.../environments/{tier}/compliance-summary` | Compliance score | team member |
| `GET` | `.../environments/{tier}/resource-usage` | Quota usage | team member |
| `GET` | `.../environments/{tier}/metrics` | Prometheus metrics | team member |
| `GET` | `.../environments/{tier}/dashboards` | Grafana links | team member |
| `POST` | `.../environments/{tier}/applications/{app}/promote` | Promote app (legacy) | team admin |
| `POST` | `.../environments/{tier}/deploy` | Deploy from catalog | team admin/developer |
| `GET` | `/api/v1/catalog/templates` | List templates | authenticated |
| `POST` | `/api/v1/catalog/templates` | Create template | platform admin |
| `GET` | `/api/v1/admin/quota-presets` | List quota presets | platform admin |
| `POST` | `/api/v1/admin/quota-presets` | Create preset | platform admin |
| `GET` | `/api/v1/admin/policy-profiles` | List policy profiles | platform admin |
| `POST` | `/api/v1/admin/policy-profiles` | Create profile | platform admin |
| `GET` | `/api/v1/audit` | Platform audit log | platform admin |
| `GET` | `/api/v1/teams/{slug}/audit` | Team audit log | team admin |

### Application Inventory (Phase 1)

| Method | Path | Description | Required Role |
|--------|------|-------------|---------------|
| `POST` | `/api/v1/teams/{slug}/applications` | Register application | team admin/developer |
| `GET` | `/api/v1/teams/{slug}/applications` | List team applications | team admin/developer |
| `GET` | `/api/v1/teams/{slug}/applications/inventory` | Team inventory grid | team admin/developer |
| `GET` | `/api/v1/teams/{slug}/applications/{name}` | Get application | team admin/developer |
| `PATCH` | `/api/v1/teams/{slug}/applications/{name}` | Update application | team admin |
| `DELETE` | `/api/v1/teams/{slug}/applications/{name}` | Delete application | team admin |
| `GET` | `.../applications/{name}/deployments` | List deployments | team admin/developer |
| `GET` | `.../applications/{name}/history` | Deployment event history | team admin/developer |
| `POST` | `.../applications/{name}/deploy` | Deploy to a tier | team admin/developer |
| `POST` | `.../applications/{name}/refresh` | Refresh Argo CD status | team admin/developer |
| `GET` | `/api/v1/applications` | List all applications | platform admin |
| `GET` | `/api/v1/applications/inventory` | Global inventory grid | platform admin |

### Promotion Requests (Phase 2)

| Method | Path | Description | Required Role |
|--------|------|-------------|---------------|
| `POST` | `.../applications/{name}/promotion-requests` | Create promotion request | team admin/developer |
| `GET` | `.../applications/{name}/promotion-requests` | List requests for app | team member |
| `GET` | `/api/v1/promotion-requests` | List all requests | platform admin |
| `GET` | `/api/v1/promotion-requests/{id}` | Get request + gate results | team member |
| `POST` | `/api/v1/promotion-requests/{id}/approve` | Approve (satisfies manual_approval) | team member (role enforced by gate) |
| `POST` | `/api/v1/promotion-requests/{id}/reject` | Reject with reason | team member |
| `POST` | `/api/v1/promotion-requests/{id}/force` | Force past failing gates | platform admin |
| `POST` | `/api/v1/promotion-requests/{id}/rollback` | Roll back a completed promotion | team admin |
| `POST` | `/api/v1/promotion-requests/{id}/cancel` | Cancel pending request | requester or team admin |

### Rollouts (Phase 2)

| Method | Path | Description | Required Role |
|--------|------|-------------|---------------|
| `GET` | `.../applications/{name}/rollout` | Rollout status (phase, step, revisions) | team admin/developer |
| `POST` | `.../applications/{name}/rollout/promote` | Promote paused rollout | team admin |
| `POST` | `.../applications/{name}/rollout/pause` | Pause rollout | team admin |
| `POST` | `.../applications/{name}/rollout/abort` | Abort rollout | team admin |

### Promotion Gates (Phase 2)

| Method | Path | Description | Required Role |
|--------|------|-------------|---------------|
| `GET` | `/api/v1/admin/promotion-gates` | List all gates (filter by scope/tier) | platform admin |
| `POST` | `/api/v1/admin/promotion-gates` | Create platform gate | platform admin |
| `DELETE` | `/api/v1/admin/promotion-gates/{id}` | Delete any gate | platform admin |
| `GET` | `.../applications/{name}/gates` | List applicable gates | team admin/developer |
| `POST` | `.../applications/{name}/gates` | Create team gate | team admin |
| `DELETE` | `.../applications/{name}/gates/{id}` | Delete team gate | team admin |

## Application Inventory

Applications are first-class: one logical application owns many deployments (one per environment tier) and is the unit that gets promoted, rolled back, and audited.

| Concept | Description |
|---------|-------------|
| Application | Logical record: name, repo URL, chart path, image repo, default strategy, owner |
| Deployment | Per-tier projection: image tag, chart version, git SHA, health, sync, strategy, timestamps |
| Inventory grid | Cross-tier view: one row per app, one column per tier (dev/staging/production), cells show image tag + health + who deployed |

Applications must be **explicitly registered** before they can be deployed. There is no auto-discovery of existing Argo CD Applications -- the tradeoff is simpler ownership tracking and deterministic audit. Catalog deploys auto-register the application on first use so casual users never hit the register step by hand.

**Register an application:**

```bash
devex app register \
  --team payments \
  --name payments-api \
  --repo https://github.com/company/payments-api \
  --chart-path deploy/helm \
  --image-repo ghcr.io/company/payments-api \
  --strategy rolling
```

**Portal:** Teams -> Payments -> Applications -> Register. The team inventory page is `Applications -> Inventory`; the global inventory is under the admin area.

## Promotion Requests and Gates

A promotion no longer fires synchronously. It creates a `PromotionRequest` that walks a state machine, running gates at each transition:

```
pending_gates -> pending_approval -> approved -> executing -> completed
                                                           \-> failed
                                                            \-> rolled_back
             \-> rejected
             \-> cancelled
```

On `create_promotion_request` the API evaluates all applicable gates. Blocking failures move the request to `rejected` (or stay `pending_gates` if the caller retries). A pending `manual_approval` gate parks the request in `pending_approval` until an authorized user approves; approval flips it to `approved`, then the executor moves it to `executing` and finally `completed`. Auto-rollback kicks in if health stays `Degraded` past the watchdog window (default 10 min), transitioning the request to `rolled_back`.

### Gate Types

Eight built-in gate types live in the registry. Team admins can add stricter gates; they cannot relax a platform gate of the same type (platform always wins on de-duplication).

| Gate Type | Config | Checks |
|-----------|--------|--------|
| `deployed_in_prior_env` | *(none)* | Prior tier has a Healthy deployment of the same app |
| `health_passing` | *(none)* | Source deployment `health_status == Healthy` |
| `min_time_in_prior_env` | `{hours: int}` | Source deployment has soaked >= N hours |
| `no_critical_cves` | *(none)* | Zero critical CVEs in source namespace (Trivy) |
| `max_high_cves` | `{max: int}` | High CVE count <= max in source namespace |
| `compliance_score_min` | `{min: int}` | Computed compliance score (violations/CVEs/events) >= min |
| `manual_approval` | `{required_role: str, count: int}` | Cleared by approval flow, not evaluation |
| `github_tag_exists` | `{repo?: str}` | The image tag exists as a tag in the upstream GitHub repo |

### Platform Mandatory Gates

Seeded by migration `006_add_promotion_governance.py`:

| Tier | Gates |
|------|-------|
| dev | *(none -- free deploys)* |
| staging | `deployed_in_prior_env`, `health_passing` |
| production | `deployed_in_prior_env`, `health_passing`, `min_time_in_prior_env(24h)`, `no_critical_cves`, `compliance_score_min(80)`, `manual_approval(admin, count=1)` |

Team admins can add extra gates (e.g. a team-specific `max_high_cves: 5` on staging, or a second `manual_approval` from a team lead). Deleting a platform gate via a team endpoint returns 403.

### Force Push and Rollback

Platform admins can force a request past a failing gate via `POST /promotion-requests/{id}/force` with a mandatory `reason` field. The reason is persisted on the request (`force_reason`, `forced_by`) and written to the audit log. Rollbacks (`POST .../rollback`) also require a reason and are restricted to team admins.

## Blue-Green and Canary Deployments

Non-rolling strategies require **Argo Rollouts** on the target cluster (already installed by PlatformForge). If Argo Rollouts is missing, the API falls back to a plain rolling update and logs a warning on the promotion request. `bluegreen` and `canary` are **production-only** -- requesting them against dev/staging is rejected at request creation.

### Chart Contract

When a promotion executes with `strategy=bluegreen|canary`, the API overrides the user's Helm values with:

| Value | Type | Set When |
|-------|------|----------|
| `deploymentStrategy` | string (`bluegreen` or `canary`) | strategy is non-rolling |
| `canarySteps` | JSON-encoded string of step list | strategy is `canary` |

The chart **MUST** conditionally render an `argoproj.io/v1alpha1/Rollout` (instead of a plain `Deployment`) when `deploymentStrategy` is set. Sketch:

```yaml
{{- if .Values.deploymentStrategy }}
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: {{ .Release.Name }}
spec:
  replicas: {{ .Values.replicas }}
  selector:
    matchLabels: { app: {{ .Release.Name }} }
  template: {{- /* same pod spec as the Deployment */ -}}
  strategy:
    {{- if eq .Values.deploymentStrategy "bluegreen" }}
    blueGreen:
      activeService: {{ .Release.Name }}
      previewService: {{ .Release.Name }}-preview
      autoPromotionEnabled: false
    {{- else if eq .Values.deploymentStrategy "canary" }}
    canary:
      steps: {{ .Values.canarySteps | fromJson | toYaml | nindent 8 }}
    {{- end }}
{{- else }}
apiVersion: apps/v1
kind: Deployment
# ... normal deployment ...
{{- end }}
```

### No Traffic Router

We deliberately do **not** use an Argo Rollouts traffic router plugin. This has two consequences:

- **Blue-green** works via Service selector swap. The preview Service receives the new version for analysis; on promote, the active Service selector flips to the new ReplicaSet (instant cutover).
- **Canary** works by replica count only. A canary step of "1 canary, 4 stable" creates 1 new-version pod alongside 4 stable pods; the Service round-robins across all 5. Actual traffic share is approximate (1/5 per request).
- **Weighted percentage traffic shifting is not supported.** A 10% canary step cannot send "10% of requests" -- it can only adjust replica counts. Real weighted routing is deferred until a Gateway API migration.

### Driving a Rollout

After a blue-green or canary promotion reaches `executing`, use the rollout endpoints (or the CLI `devex rollout` commands) to inspect and advance it:

```bash
devex rollout status payments payments-api --tier production
devex rollout promote payments payments-api --tier production   # clear pause
devex rollout pause   payments payments-api --tier production
devex rollout abort   payments payments-api --tier production
```

## Roles and Access

### Keycloak Realm Roles

| Role | Purpose | Assigned To |
|------|---------|-------------|
| `admin` | Full platform access, bypasses team membership checks | Platform administrators |
| `team-leader` | Can create new teams | Team leads and above |
| *(none)* | Can log in, view teams they belong to | All authenticated users |

### Per-Team Roles (stored in DevExForge database)

| Role | Permissions |
|------|-------------|
| `admin` | Manage members, create/delete environments, update policies, promote apps |
| `developer` | Create environments, deploy from catalog |
| `viewer` | Read-only access to team data |

Team owners are automatically assigned the `admin` role when they create a team.

### Managing Users and Access

Access control has two layers: Keycloak (authentication + platform roles) and DevExForge (team membership).

#### Adding a new user

Create the user in Keycloak via the admin console at `https://keycloak-stage.<domain>/admin`:

1. Switch to the `teams` realm (top-left dropdown)
2. Users -> Add user -> set username, email, first/last name
3. Credentials tab -> Set password (toggle "Temporary" off)
4. Role mapping tab -> Assign `team-leader` if they should be able to create teams

Or via the Keycloak API:

```bash
ADMIN_TOKEN=$(curl -sk -X POST "https://keycloak-stage.<domain>/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&client_id=admin-cli&username=admin&password=admin" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -sk -X POST "https://keycloak-stage.<domain>/admin/realms/teams/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newdev",
    "email": "newdev@company.com",
    "firstName": "New",
    "lastName": "Developer",
    "enabled": true,
    "emailVerified": true,
    "credentials": [{"type": "password", "value": "changeme", "temporary": false}]
  }'
```

#### Adding a user to a team

A team admin can add members via the CLI or API:

```bash
devex -k team members add my-team --email newdev@company.com --role developer
```

Available team roles: `admin`, `developer`, `viewer`.

#### Removing access

Remove a user from a team (keeps their Keycloak account):

```bash
devex -k team members remove my-team newdev@company.com
```

To disable a user entirely, toggle their account off in the Keycloak admin console (Users -> find user -> Enabled: OFF).

To remove a platform role (e.g. revoke team creation ability), go to Users -> Role mapping -> remove `team-leader`.

### Tiered Policy Floors

Platform enforces minimum security standards per environment tier. Teams can make policies stricter but never weaker.

| Policy | Dev | Staging | Production |
|--------|-----|---------|------------|
| requireNonRoot | false | true | true |
| requireReadOnlyRoot | false | false | true |
| maxCriticalCVEs | 5 | 0 | 0 |
| maxHighCVEs | 20 | 10 | 0 |
| requireResourceLimits | false | true | true |

## Prerequisites

- Docker (with Docker Compose)
- Python 3.12+
- Node.js 20+
- npm

## Local Development Setup

**Quick start:**

```bash
./dev/setup.sh
```

This script handles everything below automatically. If you prefer to do it step by step:

**1. Start infrastructure (PostgreSQL + Keycloak):**

```bash
docker compose up -d
```

Wait for PostgreSQL to be healthy and Keycloak to finish starting (~30s).

**2. Create a Python virtual environment and install dependencies:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./api
pip install -e ./cli
```

**3. Run database migrations:**

```bash
cd api
alembic upgrade head
cd ..
```

**4. Start the API (in one terminal):**

```bash
source .venv/bin/activate
cd api
uvicorn app.main:app --reload
```

The API is available at http://localhost:8000. OpenAPI docs at http://localhost:8000/docs.

**5. Install and start the portal (in another terminal):**

```bash
cd portal
npm install
npm run dev
```

The portal is available at http://localhost:5173.

## Services (Local Development)

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000/docs | JWT via Keycloak |
| Portal | http://localhost:5173 | Keycloak login |
| Keycloak Admin | http://localhost:8080 | admin / admin |
| PostgreSQL | localhost:5432 | devexforge / devexforge |

## Test Users

| Username | Password | Keycloak Roles |
|----------|----------|----------------|
| admin | admin123 | admin, team-leader |
| teamlead1 | password123 | team-leader |
| developer1 | password123 | (none) |

## Verifying the Setup

```bash
# Health check
curl http://localhost:8000/health

# Readiness check (verifies DB connection)
curl http://localhost:8000/ready

# Get a token and create a team
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/teams/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&client_id=devexforge-portal&username=admin&password=admin123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"displayName": "My Team", "description": "Test team"}'

# List teams
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/teams
```

## Using the CLI

```bash
source .venv/bin/activate

# Set the token for CLI usage
export DEVEXFORGE_TOKEN=$TOKEN

# Team commands
devex team list
devex team create --name "Backend Team" --description "Core services"
devex team get backend-team

# Environment commands
devex env create backend-team --tier dev
devex env list backend-team
devex env status backend-team dev
```

**Phase 1 / Phase 2 command groups:**

| Group | Purpose |
|-------|---------|
| `devex app` | Register, list, get, update, delete, deploy, refresh applications; view inventory grid |
| `devex promote` | Create, list, get, approve, reject, force, rollback, cancel promotion requests |
| `devex rollout` | Status, promote, pause, abort Argo Rollouts (blue-green/canary) |
| `devex gates` | List / create / delete promotion gates (team and platform) |

## Stopping the Environment

```bash
docker compose down      # Stop Postgres + Keycloak (keeps data)
docker compose down -v   # Stop and delete all data
```

## Running Tests

```bash
source .venv/bin/activate
cd api && python -m pytest tests/ -v
```

103 tests covering team CRUD, member management, environment lifecycle, policy floor enforcement, and health endpoints (62 Phase 1 carryover) plus gate evaluation for all 8 gate types, the promotion request state machine, rollout manifest generation for bluegreen/canary, and end-to-end router integration for applications, promotion requests, gates, and rollouts (41 Phase 2). No external dependencies required.

## CI/CD Pipeline

Travis CI runs on every push to `main`:

| Stage | What It Does |
|-------|-------------|
| **test** | Runs `pytest` on the API |
| **build** | Builds and pushes Docker images to Docker Hub (`<registry>/devexforge-{api,portal,operator}`) |
| **scan** | Trivy scans all images, fails the build on CRITICAL CVEs |
| **deploy** | Updates image tags in the private deploy repo for stage (automatic) |

### Travis CI Environment Variables

Set these in the Travis CI project settings:

| Variable | Value |
|----------|-------|
| `DOCKER_USERNAME` | Docker Hub username |
| `DOCKER_PASSWORD` | Docker Hub access token |
| `GITHUB_TOKEN_DEVEXFORGE` | GitHub PAT with repo access (for pushing to DevExForge-deploy) |

## Cluster Deployment

### First-Time Deployment

Run these steps in order. Steps 1-2 are one-time setup. Steps 3-5 deploy to stage, then prod.

**Step 1: Create your deploy repo** (one-time)

```bash
./dev/init-deploy-repo.sh
```

Generates a private GitOps repo with Argo CD Application manifests and per-environment Helm values.

**Step 2: Register DNS** (one-time, re-run if Traefik IPs change)

```bash
cd ansible
ansible-playbook playbooks/deploy-dns.yml
```

Creates 6 DNS records in Pi-hole (API, portal, Keycloak x stage/prod) pointing to the Traefik load balancer IPs. Requires PlatformForge vault secrets.

**Step 3: Bootstrap and validate stage**

```bash
./dev/bootstrap-stage.sh
./dev/smoke-test-stage.sh
```

**Step 4: Promote to production**

```bash
cd ../DevExForge-deploy
bash ../DevExForge/dev/update-image-tags.sh <tag> environments/prod/values.yaml
git add -A && git commit -m "Promote to production" && git push
```

**Step 5: Bootstrap and validate production**

```bash
./dev/bootstrap-prod.sh
./dev/smoke-test-prod.sh
```

### What Runs Where

| Component | Stage | Prod |
|-----------|:---:|:---:|
| API | yes | yes |
| Portal | yes | yes |
| Operator | yes | yes |
| PostgreSQL | yes | yes |
| Keycloak | yes | yes |

The stage API only manages the stage cluster. The prod API manages both clusters (stage for dev/staging tiers, prod for production tier).

### Promotion Flow

```
Push to main -> Travis CI builds & scans -> Stage auto-deploys via Argo CD
Validate with smoke tests -> Promote image tags to prod -> Manual Argo CD sync
```

## Developer Workflow: Deploying an Application

This section walks through the complete lifecycle of deploying a new application using DevExForge, from team creation to production.

### Portal Capabilities

| Feature | Purpose | When to Use |
|---------|---------|-------------|
| **Teams** | Organize developers into groups that own infrastructure | New project starts, new squad forms |
| **Environments** | Provision namespaces with quotas, RBAC, network policies | Team needs infrastructure to deploy services |
| **Service Catalog** | Deploy from templates (web app, API, database) via Argo CD | Developer wants to deploy without writing Helm charts |
| **Security Posture** | View Gatekeeper violations, Trivy CVEs, Falco alerts | Before promoting to production, during incidents |
| **Metrics** | Resource usage vs. quotas, Grafana dashboard links | Capacity planning, debugging performance |
| **Audit Log** | Track who changed what and when | Compliance, debugging, change tracking |
| **Admin** | Manage quota presets and policy profiles | Standardize what teams can request |
| **Promotion** | Move an app from dev -> staging -> production | After validating, promote the exact same artifact |

### Step 1: Create a team

**Portal:** Teams -> Create Team

**CLI:**
```bash
devex -k team create --name "Payments Team" --description "Payment processing services"
```

### Step 2: Add team members

**Portal:** Teams -> Payments Team -> Members -> Add Member

**CLI:**
```bash
devex -k team members add payments-team --email alice@company.com --role developer
devex -k team members add payments-team --email bob@company.com --role developer
```

### Step 3: Create a dev environment

**Portal:** Teams -> Payments Team -> Environments -> Create Environment -> tier: dev

**CLI:**
```bash
devex -k env create payments-team --tier dev
```

The operator creates namespace `payments-team-dev` with resource quotas, network policies, RBAC (only Payments team members can deploy), and Gatekeeper constraints.

### Step 4: Register the application

Register the logical application once. Subsequent deploys and promotions reference it by `team/name`.

```bash
devex -k app register \
  --team payments-team \
  --name payments-api \
  --repo https://github.com/company/payments-api \
  --chart-path deploy/helm \
  --image-repo ghcr.io/company/payments-api \
  --strategy rolling
```

**Portal:** Teams -> Payments Team -> Applications -> Register. Service Catalog deploys auto-register on first use.

### Step 5: Deploy to dev

```bash
devex -k app deploy payments-team payments-api --tier dev --image-tag v1.0.0
```

The API creates/updates the Argo CD Application in `payments-team-dev` and records a new `ApplicationDeployment` row. Check the team inventory grid in the portal (`Applications -> Inventory`) to see the dev cell populate.

Validate pods and compliance:
```bash
kubectl --context beck-stage-admin@beck-stage -n payments-team-dev get pods
devex -k app refresh payments-team payments-api
```

### Step 6: Request promotion to staging

Create the staging environment (`devex -k env create payments-team --tier staging`) and then request a promotion:

```bash
devex -k promote request payments-team payments-api --to staging
```

Gates evaluated for staging: `deployed_in_prior_env` and `health_passing`. If the dev deployment is Healthy, the request goes straight to `approved` and executes. Watch the request:

```bash
devex -k promote get <request-id>
```

### Step 7: Validate in staging

Review the Security Posture page for `payments-team-staging`. Fix any violations before requesting production promotion -- production gates will block the request otherwise.

### Step 8: Request promotion to production

```bash
devex -k env create payments-team --tier production
devex -k promote request payments-team payments-api --to production \
  --value-override replicas=3
```

Production gates run: `deployed_in_prior_env`, `health_passing`, `min_time_in_prior_env(24h)`, `no_critical_cves`, `compliance_score_min(80)`, `manual_approval(admin)`. Assuming the non-approval gates pass, the request parks in `pending_approval`:

```bash
devex -k promote approve <request-id>
```

For blue-green or canary strategies, monitor the rollout as it executes:
```bash
devex -k rollout status payments-team payments-api --tier production
```

For emergencies, roll back:
```bash
devex -k promote rollback <request-id> --reason "p99 latency regression"
```

### Step 9: Monitor

- **Metrics page:** resource usage vs. quotas, Grafana dashboard links pre-filtered to the namespace
- **Security page:** ongoing compliance monitoring, Falco runtime alerts
- **Audit log:** track all changes for compliance

### Summary

```
Create Team -> Add Members -> Create Dev Env -> Deploy App
  -> Validate in Dev
  -> Create Staging Env -> Promote to Staging
  -> Validate Security & Compliance
  -> Create Prod Env -> Promote to Production
  -> Monitor Metrics & Security
```

Each promotion carries the exact same artifact (chart version, image tag) forward. Policy floors get stricter at each tier, so if it passes staging, it meets production security requirements.
