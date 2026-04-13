# DevExForge

Developer Experience platform for Kubernetes: self-service team and namespace management with policy enforcement, built on FastAPI, React, and Kopf.

Built on top of PlatformForge, which provides the underlying Kubernetes clusters with Traefik, Argo CD, Gatekeeper, Falco, Trivy, and observability stack.

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

### Step 4: Deploy the application

**Option A -- Service Catalog (portal):**
1. Catalog -> pick a template (e.g., "Python FastAPI")
2. Select team and environment
3. Set app name, customize values (image, replicas, env vars)
4. Click Deploy

**Option B -- Argo CD directly:**
```bash
argocd app create payments-api \
  --project payments-team-dev \
  --repo https://github.com/company/payments-api.git \
  --path deploy/helm \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace payments-team-dev \
  --sync-policy automated \
  --server argocd-stage.<domain> --grpc-web --insecure
```

### Step 5: Validate in dev

Check pods are running:
```bash
kubectl --context beck-stage-admin@beck-stage -n payments-team-dev get pods
```

Check security compliance (portal: Security Posture page, or CLI):
```bash
curl -sk -H "Authorization: Bearer $TOKEN" \
  https://devexforge-api-stage.<domain>/api/v1/teams/payments-team/environments/dev/compliance-summary
```

### Step 6: Promote to staging

Create the staging environment:
```bash
devex -k env create payments-team --tier staging
```

Promote the application (portal: Applications -> Promote, or API):
```bash
curl -sk -X POST \
  "https://devexforge-api-stage.<domain>/api/v1/teams/payments-team/environments/dev/applications/payments-api/promote" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetTier": "staging"}'
```

Staging enforces stricter policies (requireNonRoot=true, maxCriticalCVEs=0). If your app runs as root or has critical CVEs, Gatekeeper will block deployment.

### Step 7: Validate in staging

Review the Security Posture page for the staging environment. Fix any violations before proceeding to production.

### Step 8: Promote to production

Create the production environment:
```bash
devex -k env create payments-team --tier production
```

Promote from staging to production with value overrides for production settings:
```bash
curl -sk -X POST \
  "https://devexforge-api-stage.<domain>/api/v1/teams/payments-team/environments/staging/applications/payments-api/promote" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"targetTier": "production", "valueOverrides": {"replicas": "3"}}'
```

Production enforces the strictest policies (requireReadOnlyRoot=true, maxHighCVEs=0).

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
