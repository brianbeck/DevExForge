import { get, post, del } from "./client";

export interface QuotaPreset {
  id: string;
  name: string;
  cpuRequest: string;
  cpuLimit: string;
  memoryRequest: string;
  memoryLimit: string;
  pods: number;
  services: number;
  pvcs: number;
  createdAt: string;
}

export interface PolicyProfile {
  id: string;
  name: string;
  maxCriticalCVEs: number;
  maxHighCVEs: number;
  requireNonRoot: boolean;
  requireReadOnlyRoot: boolean;
  requireResourceLimits: boolean;
  createdAt: string;
}

export async function listQuotaPresets(): Promise<QuotaPreset[]> {
  return get<QuotaPreset[]>("/api/v1/admin/quota-presets");
}

export async function createQuotaPreset(data: Partial<QuotaPreset>): Promise<QuotaPreset> {
  return post<QuotaPreset>("/api/v1/admin/quota-presets", data);
}

export async function deleteQuotaPreset(id: string): Promise<void> {
  return del(`/api/v1/admin/quota-presets/${id}`);
}

export async function listPolicyProfiles(): Promise<PolicyProfile[]> {
  return get<PolicyProfile[]>("/api/v1/admin/policy-profiles");
}

export async function createPolicyProfile(data: Partial<PolicyProfile>): Promise<PolicyProfile> {
  return post<PolicyProfile>("/api/v1/admin/policy-profiles", data);
}

export async function deletePolicyProfile(id: string): Promise<void> {
  return del(`/api/v1/admin/policy-profiles/${id}`);
}
