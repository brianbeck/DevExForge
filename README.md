# DevExForge

Developer Experience platform for Kubernetes: self-service team and namespace management with policy enforcement, built on FastAPI, React, and Kopf.

Built on top of [PlatformForge](https://github.com/brianbeck/PlatformForge), which provides the underlying Kubernetes clusters with Traefik, Argo CD, Gatekeeper, Falco, Trivy, and observability stack.

## Architecture

```
Portal/CLI -> API (PostgreSQL) -> Syncs CRDs to cluster -> Operator watches CRDs -> Reconciles K8s resources
```

**Components:**
- **API** (`api/`): FastAPI + PostgreSQL + Alembic, Keycloak JWT auth, tiered policy floors, multi-cluster CRD sync, application promotion
- **Portal** (`portal/`): Vite + React + TypeScript with Keycloak auth
- **Operator** (`operator/`): Kopf-based K8s operator that reconciles Team/Environment CRDs into namespaces, quotas, RBAC, NetworkPolicies, Gatekeeper constraints, and Argo CD AppProjects
- **CLI** (`cli/`): Python CLI with Click and Rich for team/environment self-service
- **Keycloak**: Identity provider with realm, client, and user management
- **CRDs** (`crds/`): Team and Environment custom resource definitions (`devexforge.brianbeck.net/v1alpha1`)
- **Helm Chart** (`deploy/helm/devexforge/`): Full deployment chart for all components including Keycloak

## Deployed Endpoints

### Stage

| Service | URL |
|---------|-----|
| API | https://devexforge-api-stage.brianbeck.net |
| Portal | https://devexforge-stage.brianbeck.net |
| Keycloak | https://keycloak-stage.brianbeck.net |
| Argo CD | https://argocd-stage.brianbeck.net |

### Production

| Service | URL |
|---------|-----|
| API | https://devexforge-api.brianbeck.net |
| Portal | https://devexforge.brianbeck.net |
| Keycloak | https://keycloak.brianbeck.net |
| Argo CD | https://argocd-prod.brianbeck.net |

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
| `POST` | `.../environments/{tier}/applications/{app}/promote` | Promote app | team admin |
| `POST` | `.../environments/{tier}/deploy` | Deploy from catalog | team admin/developer |
| `GET` | `/api/v1/catalog/templates` | List templates | authenticated |
| `POST` | `/api/v1/catalog/templates` | Create template | platform admin |
| `GET` | `/api/v1/admin/quota-presets` | List quota presets | platform admin |
| `POST` | `/api/v1/admin/quota-presets` | Create preset | platform admin |
| `GET` | `/api/v1/admin/policy-profiles` | List policy profiles | platform admin |
| `POST` | `/api/v1/admin/policy-profiles` | Create profile | platform admin |
| `GET` | `/api/v1/audit` | Platform audit log | platform admin |
| `GET` | `/api/v1/teams/{slug}/audit` | Team audit log | team admin |

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

35 tests covering team CRUD, member management, environment lifecycle, policy floor enforcement, and health endpoints. No external dependencies required.

## CI/CD Pipeline

Travis CI runs on every push to `main`:

| Stage | What It Does |
|-------|-------------|
| **test** | Runs `pytest` on the API |
| **build** | Builds and pushes Docker images to Docker Hub (`brianbeck/devexforge-{api,portal,operator}`) |
| **scan** | Trivy scans all images, fails the build on CRITICAL CVEs |
| **deploy** | Updates image tags in [DevExForge-deploy](https://github.com/brianbeck/DevExForge-deploy) for stage (automatic) |

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
