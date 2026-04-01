export interface ResourceQuotaSpec {
  cpuRequests: string;
  cpuLimits: string;
  memoryRequests: string;
  memoryLimits: string;
  pods: number;
  services: number;
  persistentVolumeClaims: number;
  storageRequests: string;
}

export interface LimitRangeSpec {
  defaultCpuRequest: string;
  defaultCpuLimit: string;
  defaultMemoryRequest: string;
  defaultMemoryLimit: string;
  maxCpuLimit: string;
  maxMemoryLimit: string;
}

export interface NetworkPolicySpec {
  allowInterNamespace: boolean;
  allowedNamespaces: string[];
  allowedExternalCidrs: string[];
  denyAllEgress: boolean;
}

export interface PoliciesSpec {
  allowPrivilegedContainers: boolean;
  allowHostNetwork: boolean;
  allowedImageRegistries: string[];
  requiredLabels: string[];
}

export interface ArgoCDSpec {
  enabled: boolean;
  project: string;
  sourceRepos: string[];
  destinations: string[];
}

export interface Environment {
  id: string;
  teamSlug: string;
  tier: "dev" | "staging" | "prod";
  namespaceName: string;
  phase: "Pending" | "Active" | "Error" | "Deleting";
  resourceQuota: ResourceQuotaSpec;
  limitRange: LimitRangeSpec;
  networkPolicy: NetworkPolicySpec;
  policies: PoliciesSpec;
  argocd: ArgoCDSpec;
  resourcesCreated: Record<string, boolean>;
  createdAt: string;
  updatedAt: string;
}

export interface EnvironmentCreate {
  tier: "dev" | "staging" | "prod";
  resourceQuota?: Partial<ResourceQuotaSpec>;
  limitRange?: Partial<LimitRangeSpec>;
  networkPolicy?: Partial<NetworkPolicySpec>;
  policies?: Partial<PoliciesSpec>;
  argocd?: Partial<ArgoCDSpec>;
}

export interface EnvironmentUpdate {
  resourceQuota?: Partial<ResourceQuotaSpec>;
  limitRange?: Partial<LimitRangeSpec>;
  networkPolicy?: Partial<NetworkPolicySpec>;
  policies?: Partial<PoliciesSpec>;
  argocd?: Partial<ArgoCDSpec>;
}

export interface Member {
  id: string;
  email: string;
  role: "owner" | "admin" | "developer" | "viewer";
  addedAt: string;
}

export interface MemberCreate {
  email: string;
  role: "admin" | "developer" | "viewer";
}

export interface Team {
  slug: string;
  displayName: string;
  description: string;
  ownerEmail: string;
  costCenter: string;
  tags: Record<string, string>;
  memberCount: number;
  environmentCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface TeamCreate {
  slug: string;
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
  page: number;
  pageSize: number;
}
