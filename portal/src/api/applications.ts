import { get, post, patch, del } from "./client";

export interface Application {
  id: string;
  slug: string;
  name: string;
  displayName: string;
  description: string | null;
  repoUrl: string | null;
  chartPath: string | null;
  chartRepoUrl: string | null;
  ownerEmail: string;
  defaultStrategy: "rolling" | "bluegreen" | "canary";
  canarySteps: unknown | null;
  metadata: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApplicationDeployment {
  id: string;
  environmentTier: string;
  environmentId: string;
  namespaceName: string;
  argocdAppName: string;
  imageTag: string | null;
  chartVersion: string | null;
  gitSha: string | null;
  healthStatus: string | null;
  syncStatus: string | null;
  strategy: string;
  deployedAt: string;
  deployedBy: string;
  lastSyncedAt: string | null;
}

export interface ApplicationDetail extends Application {
  deployments: ApplicationDeployment[];
}

export interface ApplicationCreate {
  name: string;
  displayName: string;
  description?: string;
  repoUrl?: string;
  chartPath?: string;
  chartRepoUrl?: string;
  ownerEmail: string;
  defaultStrategy?: "rolling" | "bluegreen" | "canary";
  metadata?: Record<string, unknown>;
}

export interface ApplicationUpdate {
  displayName?: string;
  description?: string;
  repoUrl?: string;
  chartPath?: string;
  chartRepoUrl?: string;
  ownerEmail?: string;
  defaultStrategy?: "rolling" | "bluegreen" | "canary";
  metadata?: Record<string, unknown>;
}

export interface ApplicationDeployRequest {
  tier: "dev" | "staging" | "production";
  imageTag?: string;
  chartVersion?: string;
  gitSha?: string;
  valueOverrides?: Record<string, unknown>;
  strategy?: "rolling" | "bluegreen" | "canary";
}

export interface InventoryCell {
  imageTag: string | null;
  deployedAt: string | null;
  deployedBy: string | null;
  healthStatus: string | null;
  syncStatus: string | null;
}

export interface InventoryRow {
  id: string;
  name: string;
  displayName: string;
  ownerEmail: string;
  teamSlug: string;
  deployments: Record<string, InventoryCell | null>;
}

export interface InventoryResponse {
  rows: InventoryRow[];
  total: number;
}

export interface DeploymentEvent {
  id: number;
  deploymentId: string;
  eventType: string;
  fromVersion: string | null;
  toVersion: string | null;
  actor: string;
  details: Record<string, unknown> | null;
  occurredAt: string;
}

export interface DeploymentHistory {
  events: DeploymentEvent[];
  total: number;
}

export function listApplications(slug: string): Promise<Application[]> {
  return get<Application[]>(`/api/v1/teams/${slug}/applications`);
}

export function getApplication(
  slug: string,
  name: string
): Promise<ApplicationDetail> {
  return get<ApplicationDetail>(
    `/api/v1/teams/${slug}/applications/${name}`
  );
}

export function createApplication(
  slug: string,
  data: ApplicationCreate
): Promise<Application> {
  return post<Application>(`/api/v1/teams/${slug}/applications`, data);
}

export function updateApplication(
  slug: string,
  name: string,
  data: ApplicationUpdate
): Promise<Application> {
  return patch<Application>(
    `/api/v1/teams/${slug}/applications/${name}`,
    data
  );
}

export function deleteApplication(
  slug: string,
  name: string
): Promise<void> {
  return del(`/api/v1/teams/${slug}/applications/${name}`);
}

export function deployApplication(
  slug: string,
  name: string,
  data: ApplicationDeployRequest
): Promise<ApplicationDeployment> {
  return post<ApplicationDeployment>(
    `/api/v1/teams/${slug}/applications/${name}/deploy`,
    data
  );
}

export function refreshApplication(
  slug: string,
  name: string
): Promise<ApplicationDetail> {
  return post<ApplicationDetail>(
    `/api/v1/teams/${slug}/applications/${name}/refresh`,
    {}
  );
}

export function getTeamInventory(slug: string): Promise<InventoryResponse> {
  return get<InventoryResponse>(
    `/api/v1/teams/${slug}/applications/inventory`
  );
}

export function getGlobalInventory(): Promise<InventoryResponse> {
  return get<InventoryResponse>(`/api/v1/applications/inventory`);
}

export function getHistory(
  slug: string,
  name: string
): Promise<DeploymentHistory> {
  return get<DeploymentHistory>(
    `/api/v1/teams/${slug}/applications/${name}/history`
  );
}
