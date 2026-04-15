# DevExForge API

FastAPI service backing the DevExForge platform. Async SQLAlchemy on PostgreSQL,
Alembic migrations, Keycloak JWT auth. Runs in the production cluster and
manages both stage and prod via a multi-cluster kubeconfig.

See the top-level [README](../README.md) for endpoint reference and the full
architecture overview.

## Layout

| Path                  | Contents                                              |
| --------------------- | ----------------------------------------------------- |
| `app/routers/`        | FastAPI route handlers (teams, envs, apps, promotions, rollouts, gates, catalog, audit, observability, security, admin, health) |
| `app/services/`       | Business logic layer (see key services below)        |
| `app/models/`         | SQLAlchemy ORM models                                 |
| `app/schemas/`        | Pydantic request/response schemas                     |
| `app/middleware/`     | Auth, logging, error handling                         |
| `alembic/versions/`   | Database migrations                                   |
| `tests/`              | Pytest suite                                          |

## Key Services

| Service                          | Responsibility                                                              |
| -------------------------------- | --------------------------------------------------------------------------- |
| `application_service`            | Register / list / deploy applications, image repo bookkeeping               |
| `promotion_service`              | Promotion request lifecycle (request, approve, reject, force, rollback)    |
| `gate_service`                   | Promotion gate evaluation and admin gate CRUD                               |
| `rollout_service`                | Argo Rollouts status, promote, pause, abort                                 |
| `k8s_service`                    | Multi-cluster kube client plus Argo CD Application CR writes                |
| `argocd_sync`                    | Background loop polling Argo CD, advisory-locked for multi-replica safety   |

## Background Sync Loop

`argocd_sync` runs every 30 seconds. It:

- Polls Argo CD Applications for each tracked deployment and updates status
  in PostgreSQL.
- Monitors in-flight promotions and triggers auto-rollback when an application
  fails its post-deploy gates.
- Uses a PostgreSQL advisory lock so only one replica runs the loop at a time.

## Running Locally

```bash
cd api
alembic upgrade head
uvicorn app.main:app --reload
```

The API listens on `:8000`. Requires Postgres and Keycloak running locally
(use `./dev/setup.sh` from the repo root).

## Tests

```bash
python -m pytest tests/ -v
```

Current suite: 103 tests covering routers, services, and the Argo CD sync
loop.

## Migrations

| Revision | Summary                                           |
| -------- | ------------------------------------------------- |
| `001`    | Initial schema (teams, environments)              |
| `002`    | Add `cluster` column                              |
| `003`    | Catalog and admin tables                          |
| `004`    | Constraints, indexes, `updated_at` triggers       |
| `005`    | Applications                                      |
| `006`    | Promotion governance (requests, gates, approvals) |
| `007`    | `image_repo` column on applications               |

Create a new migration with `alembic revision -m "..."` and apply with
`alembic upgrade head`.
