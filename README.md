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
| `GITHUB_TOKEN` | GitHub PAT with repo access (for pushing to DevExForge-deploy) |

## Cluster Deployment

### Setting Up Your Deploy Repo

Run the setup script to generate a private GitOps repo configured for your environment:

```bash
./dev/init-deploy-repo.sh
```

It will prompt for your GitHub username, Docker Hub username, cluster contexts, and domain. It creates the repo structure, Argo CD Application manifests, and per-environment Helm values -- all wired to your infrastructure.

Deployments are managed via GitOps through the deploy repo and Argo CD.

The API runs in the production cluster (production SLAs). The operator is deployed per-cluster.

| Tier | Cluster | What Runs |
|------|---------|-----------|
| dev | beck-stage | Operator |
| staging | beck-stage | Operator |
| production | beck-prod | API, Portal, Operator, PostgreSQL |

### Promotion Flow

```
Push to main -> Travis CI builds & scans -> Stage auto-deploys via Argo CD
To promote to prod -> PR to DevExForge-deploy -> Merge -> Manual Argo CD sync
```
