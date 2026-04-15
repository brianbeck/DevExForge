# devex CLI

Click-based Python CLI for self-service team, environment, application, and
promotion operations against the DevExForge API. Uses Rich for output.

See the top-level [README](../README.md) for platform architecture and API
endpoint reference.

## Install

```bash
cd cli
pip install -e .
```

This installs the `devex` entrypoint.

## Authentication

Auth is profile-based. Profiles live in `~/.config/devex/config.toml` and
store the API URL, realm, client ID, and a cached token obtained from
Keycloak.

```bash
devex login --profile dev --api-url https://api.example.com
devex profile list
devex profile use dev
```

## Command Groups

| Command                | Purpose                                                       |
| ---------------------- | ------------------------------------------------------------- |
| `devex login`          | Obtain a Keycloak token and store it in the active profile    |
| `devex profile`        | List, add, use, and delete profiles                           |
| `devex team`           | CRUD teams; nested `devex team members` manages membership    |
| `devex env`            | Create, list, get, and delete environments                    |
| `devex app`            | `register`, `list`, `get`, `delete`, `deploy`, `history`, `inventory`, `refresh` |
| `devex promote`        | `request`, `list`, `get`, `approve`, `reject`, `force`, `rollback`, `cancel` |
| `devex rollout`        | `status`, `promote`, `pause`, `abort` (Argo Rollouts control) |
| `devex gates`          | `list`, `add`, `remove` promotion gates (admin only)          |

## Example Flow

```bash
# Register a new application
devex app register --team backend-platform --name orders-api \
    --repo https://github.com/acme/orders-api --image-repo ghcr.io/acme/orders-api

# Deploy to dev
devex app deploy orders-api --env dev --image-tag v1.2.3

# Request promotion dev -> staging
devex promote request --app orders-api --from dev --to staging

# Approve the request (requires approver role)
devex promote list --status pending
devex promote approve <request-id>

# Roll back if it misbehaves in staging
devex promote rollback --app orders-api --env staging
```

## Common Flags

| Flag           | Meaning                                                    |
| -------------- | ---------------------------------------------------------- |
| `--api-url`    | Override the API URL for a single invocation               |
| `--token`      | Supply a bearer token directly (bypasses the profile)      |
| `--profile`    | Select a named profile                                     |
| `-k`           | Skip TLS verification (for local dev against self-signed)  |
