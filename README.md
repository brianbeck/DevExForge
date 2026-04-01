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
- **CRDs** (`crds/`): Team and Environment custom resource definitions (`devexforge.brianbeck.net/v1alpha1`)
- **Helm Chart** (`deploy/helm/devexforge/`): Full deployment chart for all components

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

## Services

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000/docs | JWT via Keycloak |
| Portal | http://localhost:5173 | Keycloak login |
| Keycloak Admin | http://localhost:8080 | admin / admin |
| PostgreSQL | localhost:5432 | devexforge / devexforge |

## Test Users

| Username | Password | Roles |
|----------|----------|-------|
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

## Cluster Deployment

The API runs in the production cluster (production SLAs). The operator is deployed per-cluster. Tier mapping:

| Tier | Cluster |
|------|---------|
| dev | beck-stage |
| staging | beck-stage |
| production | beck-prod |

Deploy via Helm:

```bash
helm install devexforge deploy/helm/devexforge -f values-prod.yaml
```

Or via Argo CD by pointing an Application at `deploy/helm/devexforge/`.
