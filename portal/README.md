# DevExForge Portal

Vite + React + TypeScript single-page app with Keycloak SSO. Talks to the
DevExForge API on behalf of the logged-in user.

See the top-level [README](../README.md) for platform architecture.

## Stack

| Piece         | Version / Notes                              |
| ------------- | -------------------------------------------- |
| Vite          | Dev server and build                         |
| React         | 18 with function components and hooks        |
| TypeScript    | Strict mode                                  |
| react-router  | Client-side routing                          |
| keycloak-js   | OIDC login against the platform Keycloak     |

## Layout

| Path               | Contents                                              |
| ------------------ | ----------------------------------------------------- |
| `src/api/`         | Typed fetch clients (one module per API surface)      |
| `src/pages/`       | Top-level routed pages                                |
| `src/components/`  | Shared components (`Layout`, `ProtectedRoute`)        |
| `src/types/`       | Shared TS types                                       |
| `src/config.ts`    | Runtime config (API base URL, Keycloak realm/client)  |

## Running Locally

```bash
cd portal
npm install
npm run dev
```

The dev server listens on `:5173`. The API must be reachable at the URL
configured in `src/config.ts` (defaults to `http://localhost:8000`).

## Type Check

```bash
npx tsc --noEmit
```

## Pages

| Area            | Pages                                                                 |
| --------------- | --------------------------------------------------------------------- |
| Auth            | `LoginPage`                                                           |
| Teams           | `TeamsListPage`, `TeamDetailPage`, `MembersPage`                      |
| Environments    | `EnvironmentsPage`, `EnvironmentDetailPage` (also embedded in team detail) |
| Applications    | `ApplicationsPage`, `ApplicationDetailPage`, `GlobalInventoryPage`    |
| Promotions      | `PromotionsPage`, `PromotionRequestDetailPage`, `RolloutStatusPage`   |
| Admin           | `AdminPage`, `AdminGatesPage`                                         |
| Catalog         | `CatalogPage`                                                         |
| Audit           | `AuditLogPage`                                                        |
| Security        | `SecurityPage`                                                        |
| Metrics         | `MetricsPage`                                                         |

## Admin Visibility

Admin-gated nav entries (Admin, Gates, and similar) are rendered only when
the Keycloak token's `realm_access.roles` contains the `devexforge-admin`
role. Non-admin users simply do not see those links, and the API enforces
the same boundary server-side.
