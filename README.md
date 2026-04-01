# Platform Engineering Architect Course

Welcome to the companion repo for PlatformEngineering.org Architect course! This hands-on set of mini-projects will have you do exercises for building platform concepts you learn about in the course with monitoring, policy management, security operations, and team management capabilities.


## 🎯 Learning Objectives

By the end of this workshop, you will:
- Set up a complete Kubernetes-based engineering platform
- Implement policy-as-code with Open Policy Agent (OPA) Gatekeeper
- Configure monitoring and alerting with Grafana stack
- Deploy security monitoring with Falco
- Build and manage engineering teams through APIs and UIs

## 📋 System Requirements

Before starting, ensure your system meets these requirements:
- Decent internet connection recommended for accessing coder.com environments

Optional:
- Visual Studio Code has a coder.com remote extension, where you can access your coder.com environment from your local VS Code instead of using it in the browser.

### Required Software
- None: We will use coder.com environments

### Recommended supplemental material
- Recommended, not required - [Effective Platform Engineering](https://effectiveplatformengineering.com)

### Prerequisite

Install Helm:

```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
```

The Grafana stack includes Prometheus, Grafana, AlertManager, and other monitoring tools.

### Verify Prerequisites
```bash
# Check Docker
docker --version

# Check Kubernetes
kubectl cluster-info

# Check Helm
helm version

# Check Python
python3 --version

# Check Node.js
node --version
```
Sometimes, you might find that some of these are missing. Use apt-get, and / or curl to try and update these packages as you would do it on your local laptop environment.
## 🚀 Getting Started

**⚠️ IMPORTANT: Start with the Foundation module first!**

1. **Begin Here**: Navigate to [`foundation/README.md`](foundation/README.md)
2. Complete all foundation setup before proceeding to other modules
3. Follow the modules in the recommended order below

## 📚 Workshop Modules

### 1. 🏗️ Foundation (`01_foundation/`) - **START HERE**

Contains the fundamental setup for your Kubernetes environment including:
- Kubernetes cluster verification
- Grafana monitoring stack installation
- OPA Gatekeeper policy engine setup
- Initial health checks and verification

**Key Deliverables:**
- Functioning Kubernetes cluster
- Grafana dashboard accessible
- Gatekeeper policies working

---

### 2. 🛡️ CapOc (`capoc/`) - Compliance at Point of Change
**Prerequisites**: Foundation module completed

Focuses on implementing compliance and quality controls:
- **CVE Module**: Container vulnerability scanning and policies
- **Quality Module**: Code quality gates and enforcement

**Key Deliverables:**
- CVE scanning policies active
- Quality gates preventing bad deployments
- Working constraint templates and policies

---

### 3. 🔒 SecOps (`secops/`) - Security Operations

Dedicated to security monitoring and threat detection:
- Falco runtime security monitoring
- Custom security rules and alerts
- Security policy enforcement

**Key Deliverables:**
- Falco deployed and monitoring
- Security alerts working
- Custom security rules active

---

### 4. 👥 Teams Management (`teams-management/`) - Platform APIs & UX (Legacy)

Original module covering engineering platform APIs and developer experience.
This has been superseded by the DevExForge platform below, but is kept as reference.

---

### 5. DevExForge Platform (`api/`, `portal/`, `operator/`, `cli/`)

Production-grade developer experience platform built on PlatformForge. Replaces
the teams-management module with PostgreSQL persistence, CRD-based operator,
React portal, and multi-cluster support.

**Components:**
- **API** (`api/`): FastAPI + PostgreSQL + Alembic, Keycloak JWT auth, tiered policy floors, multi-cluster CRD sync, application promotion
- **Portal** (`portal/`): Vite + React + TypeScript with Keycloak auth
- **Operator** (`operator/`): Kopf-based K8s operator that reconciles Team/Environment CRDs into namespaces, quotas, RBAC, NetworkPolicies, Gatekeeper constraints, and Argo CD AppProjects
- **CLI** (`cli/`): Python CLI with Click and Rich for team/environment self-service
- **CRDs** (`crds/`): Team and Environment custom resource definitions (`devexforge.brianbeck.net/v1alpha1`)
- **Helm Chart** (`deploy/helm/devexforge/`): Full deployment chart for all components

#### Prerequisites

- Docker (with Docker Compose)
- Python 3.12+
- Node.js 20+
- npm

#### Local Development Setup

**Quick start:**

```bash
./dev/setup.sh
```

This script handles everything below automatically. If you prefer to do it
step by step:

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

#### Services

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000/docs | JWT via Keycloak |
| Portal | http://localhost:5173 | Keycloak login |
| Keycloak Admin | http://localhost:8080 | admin / admin |
| PostgreSQL | localhost:5432 | devexforge / devexforge |

#### Test Users

| Username | Password | Roles |
|----------|----------|-------|
| admin | admin123 | admin, team-leader |
| teamlead1 | password123 | team-leader |
| developer1 | password123 | (none) |

#### Verifying the Setup

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

#### Using the CLI

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

#### Stopping the Environment

```bash
docker compose down      # Stop Postgres + Keycloak (keeps data)
docker compose down -v   # Stop and delete all data
```

**Key Deliverables:**
- Working Teams API with CRUD operations, PostgreSQL persistence, and Keycloak auth
- Functional CLI tool
- React developer portal
- Tiered policy floors enforced per environment tier
- Multi-cluster CRD sync (stage + prod)
- Application promotion between environments via Argo CD
- Kopf operator reconciling namespaces, quotas, RBAC, NetworkPolicies, and Gatekeeper constraints

## ✅ Module Completion Checklist

### Foundation ✅
- [ ] Kubernetes cluster accessible
- [ ] Grafana dashboard working
- [ ] Gatekeeper policies deployed
- [ ] All health checks passing

### CapOc ✅
- [ ] CVE scanning active
- [ ] Quality policies enforced
- [ ] Constraint templates working

### SecOps ✅
- [ ] Falco monitoring active
- [ ] Security alerts configured
- [ ] Custom rules deployed

### Teams Management ✅
- [ ] Teams API responding
- [ ] CLI tool functional
- [ ] Web UI accessible
- [ ] End-to-end team workflow working
- [ ] Kubernetes operator deployed and working (responds/creates team namespaces based on api usage)

## 🆘 Troubleshooting & Support

### Common Issues

**Kubernetes Connection Issues**
```bash
# Verify cluster connection
kubectl cluster-info
kubectl get nodes

# Check cluster resources
kubectl top nodes
kubectl get pods --all-namespaces
```

**Resource Constraints**
```bash
# Check resource usage
kubectl top nodes
kubectl describe nodes

# Scale down components if needed
kubectl scale deployment <deployment-name> --replicas=1
```

**Port Conflicts**
- Grafana: Default port 3000
- Teams UI: Default port 4200
- Teams API: Default port 8080

### Getting Help

1. **Check module-specific README files** for detailed troubleshooting
2. **Review pod logs** for specific error messages:
   ```bash
   kubectl logs <pod-name> -n <namespace>
   ```
3. **Verify prerequisite installations** before proceeding
4. **Reach out to facilitators** for assistance

## 📖 Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [OPA Gatekeeper Guide](https://open-policy-agent.github.io/gatekeeper/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Falco Documentation](https://falco.org/docs/)

---

**Ready to begin?** 🎯 Head to the [`foundation/README.md`](foundation/README.md) to start your engineering platform journey!

