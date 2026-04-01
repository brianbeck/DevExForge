export interface ResourceQuotaSpec {
  cpuRequest: string;
  cpuLimit: string;
  memoryRequest: string;
  memoryLimit: string;
  pods: number;
  services: number;
  persistentVolumeClaims: number;
}

export interface LimitRangeSpec {
  defaultCpuRequest: string;
  defaultCpuLimit: string;
  defaultMemoryRequest: string;
  defaultMemoryLimit: string;
}

export interface NetworkPolicySpec {
  allowInterNamespace: boolean;
  allowedNamespaces: string[];
  egressAllowInternet: boolean;
}

export interface PoliciesSpec {
  maxCriticalCVEs: number;
  maxHighCVEs: number;
  requireNonRoot: boolean;
  requireReadOnlyRoot: boolean;
  requireResourceLimits: boolean;
  exemptions?: {
    exemptImages: string[];
    exemptNamespaces: string[];
  } | null;
}

export interface ArgoCDSpec {
  enabled: boolean;
  sourceRepos: string[];
  allowedClusterResources: { group: string; kind: string }[];
}

export interface Environment {
  id: string;
  teamSlug: string;
  tier: "dev" | "staging" | "production";
  namespaceName: string;
  cluster: string | null;
  phase: "Pending" | "Provisioning" | "Active" | "Error" | "Deleting";
  resourceQuota: ResourceQuotaSpec | null;
  limitRange: LimitRangeSpec | null;
  networkPolicy: NetworkPolicySpec | null;
  policies: PoliciesSpec | null;
  argoCD: ArgoCDSpec | null;
  createdAt: string;
  updatedAt: string;
}

export interface EnvironmentCreate {
  tier: "dev" | "staging" | "production";
  resourceQuota?: Partial<ResourceQuotaSpec>;
  limitRange?: Partial<LimitRangeSpec>;
  networkPolicy?: Partial<NetworkPolicySpec>;
  policies?: Partial<PoliciesSpec>;
  argoCD?: Partial<ArgoCDSpec>;
}

export interface EnvironmentUpdate {
  resourceQuota?: Partial<ResourceQuotaSpec>;
  limitRange?: Partial<LimitRangeSpec>;
  networkPolicy?: Partial<NetworkPolicySpec>;
  policies?: Partial<PoliciesSpec>;
  argoCD?: Partial<ArgoCDSpec>;
}

export interface Member {
  email: string;
  keycloakId: string | null;
  role: "admin" | "developer" | "viewer";
  addedAt: string;
}

export interface MemberCreate {
  email: string;
  role: "admin" | "developer" | "viewer";
}

export interface Team {
  id: string;
  slug: string;
  displayName: string;
  description: string | null;
  costCenter: string | null;
  tags: Record<string, string>;
  ownerEmail: string;
  memberCount: number;
  environmentCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface TeamCreate {
  displayName: string;
  description?: string;
  costCenter?: string;
  tags?: Record<string, string>;
}

export interface TeamUpdate {
  displayName?: string;
  description?: string;
  costCenter?: string;
  tags?: Record<string, string>;
}

export interface TeamListResponse {
  teams: Team[];
  total: number;
}
