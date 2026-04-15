import { get, post, del } from "./client";

export type PromotionStatus =
  | "pending_gates"
  | "pending_approval"
  | "approved"
  | "executing"
  | "completed"
  | "rejected"
  | "failed"
  | "rolled_back"
  | "cancelled";

export type Tier = "dev" | "staging" | "production";
export type Strategy = "rolling" | "bluegreen" | "canary";

export interface PromotionGate {
  id: string;
  gateType: string;
  scope: "platform" | "team";
  tier: Tier | null;
  enforcement: "blocking" | "advisory";
  config: Record<string, unknown>;
  createdBy: string;
  createdAt: string;
}

export interface GateResult {
  id?: string;
  gateId: string;
  gateType: string;
  passed: boolean;
  message: string | null;
  evaluatedAt: string;
  details?: Record<string, unknown> | null;
}

export interface PromotionRequest {
  id: string;
  applicationId: string;
  applicationName: string | null;
  teamSlug: string | null;
  fromTier: Tier | null;
  targetTier: Tier;
  imageTag: string | null;
  chartVersion: string | null;
  gitSha: string | null;
  strategy: Strategy | null;
  status: PromotionStatus;
  notes: string | null;
  requestedBy: string;
  requestedAt: string;
  approverEmail: string | null;
  approvedAt: string | null;
  rejectionReason: string | null;
  forceReason: string | null;
  forcedBy: string | null;
  executedAt: string | null;
  completedAt: string | null;
  rollbackRevision: string | null;
}

export interface PromotionRequestDetail extends PromotionRequest {
  gateResults: GateResult[];
}

export interface PromotionCreate {
  targetTier: Tier;
  imageTag?: string;
  chartVersion?: string;
  gitSha?: string;
  strategy?: Strategy;
  notes?: string;
}

export interface RolloutStatus {
  strategy: Strategy;
  phase: string;
  currentStepIndex: number | null;
  totalSteps: number | null;
  stableRevision: string | null;
  canaryRevision: string | null;
  activeService: string | null;
  previewService: string | null;
  message: string | null;
}

export interface PlatformGateCreate {
  gateType: string;
  tier: Tier | null;
  enforcement: "blocking" | "advisory";
  config: Record<string, unknown>;
}

export interface TeamGateCreate {
  gateType: string;
  enforcement: "blocking" | "advisory";
  config: Record<string, unknown>;
}

// Promotion requests

export function createPromotionRequest(
  teamSlug: string,
  appName: string,
  body: PromotionCreate
): Promise<PromotionRequestDetail> {
  return post<PromotionRequestDetail>(
    `/api/v1/teams/${teamSlug}/applications/${appName}/promotion-requests`,
    body
  );
}

export function listTeamPromotions(
  teamSlug: string,
  appName: string
): Promise<PromotionRequest[]> {
  return get<{ items: PromotionRequest[]; total: number }>(
    `/api/v1/teams/${teamSlug}/applications/${appName}/promotion-requests`
  ).then((r) => r.items);
}

export function listAllPromotions(
  status?: string,
  tier?: string
): Promise<PromotionRequest[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (tier) params.set("tier", tier);
  const qs = params.toString();
  return get<{ items: PromotionRequest[]; total: number }>(
    `/api/v1/promotion-requests${qs ? `?${qs}` : ""}`
  ).then((r) => r.items);
}

export function getPromotion(id: string): Promise<PromotionRequestDetail> {
  return get<PromotionRequestDetail>(`/api/v1/promotion-requests/${id}`);
}

export function approvePromotion(
  id: string,
  notes?: string
): Promise<PromotionRequestDetail> {
  return post<PromotionRequestDetail>(
    `/api/v1/promotion-requests/${id}/approve`,
    { notes }
  );
}

export function rejectPromotion(
  id: string,
  reason: string
): Promise<PromotionRequestDetail> {
  return post<PromotionRequestDetail>(
    `/api/v1/promotion-requests/${id}/reject`,
    { reason }
  );
}

export function forcePromotion(
  id: string,
  reason: string
): Promise<PromotionRequestDetail> {
  return post<PromotionRequestDetail>(
    `/api/v1/promotion-requests/${id}/force`,
    { reason }
  );
}

export function rollbackPromotion(
  id: string,
  reason: string
): Promise<PromotionRequestDetail> {
  return post<PromotionRequestDetail>(
    `/api/v1/promotion-requests/${id}/rollback`,
    { reason }
  );
}

export function cancelPromotion(
  id: string
): Promise<PromotionRequestDetail> {
  return post<PromotionRequestDetail>(
    `/api/v1/promotion-requests/${id}/cancel`,
    {}
  );
}

// Rollouts

export function getRolloutStatus(
  teamSlug: string,
  appName: string,
  tier: Tier
): Promise<RolloutStatus> {
  return get<RolloutStatus>(
    `/api/v1/teams/${teamSlug}/applications/${appName}/rollout/${tier}`
  );
}

export function promoteRollout(
  teamSlug: string,
  appName: string,
  tier: Tier
): Promise<RolloutStatus> {
  return post<RolloutStatus>(
    `/api/v1/teams/${teamSlug}/applications/${appName}/rollout/${tier}/promote`,
    {}
  );
}

export function pauseRollout(
  teamSlug: string,
  appName: string,
  tier: Tier
): Promise<RolloutStatus> {
  return post<RolloutStatus>(
    `/api/v1/teams/${teamSlug}/applications/${appName}/rollout/${tier}/pause`,
    {}
  );
}

export function abortRollout(
  teamSlug: string,
  appName: string,
  tier: Tier
): Promise<RolloutStatus> {
  return post<RolloutStatus>(
    `/api/v1/teams/${teamSlug}/applications/${appName}/rollout/${tier}/abort`,
    {}
  );
}

// Gates

export function listApplicableGates(
  teamSlug: string,
  appName: string
): Promise<PromotionGate[]> {
  return get<PromotionGate[]>(
    `/api/v1/teams/${teamSlug}/applications/${appName}/gates`
  );
}

export function addTeamGate(
  teamSlug: string,
  appName: string,
  body: TeamGateCreate
): Promise<PromotionGate> {
  return post<PromotionGate>(
    `/api/v1/teams/${teamSlug}/applications/${appName}/gates`,
    body
  );
}

export function removeTeamGate(
  teamSlug: string,
  appName: string,
  gateId: string
): Promise<void> {
  return del(
    `/api/v1/teams/${teamSlug}/applications/${appName}/gates/${gateId}`
  );
}

export function listAllGates(
  scope?: string,
  tier?: string
): Promise<PromotionGate[]> {
  const params = new URLSearchParams();
  if (scope) params.set("scope", scope);
  if (tier) params.set("tier", tier);
  const qs = params.toString();
  return get<{ items: PromotionGate[]; total: number }>(
    `/api/v1/admin/promotion-gates${qs ? `?${qs}` : ""}`
  ).then((r) => r.items);
}

export function createPlatformGate(
  body: PlatformGateCreate
): Promise<PromotionGate> {
  return post<PromotionGate>(`/api/v1/admin/promotion-gates`, body);
}

export function deletePlatformGate(id: string): Promise<void> {
  return del(`/api/v1/admin/promotion-gates/${id}`);
}
