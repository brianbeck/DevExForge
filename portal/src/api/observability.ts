import { get } from "./client";

export interface ResourceQuotaUsage {
  name: string;
  hard: Record<string, string>;
  used: Record<string, string>;
}

export interface Dashboard {
  name: string;
  url: string;
}

export async function getResourceUsage(slug: string, tier: string) {
  return get<{ namespace: string; cluster: string; quotas: ResourceQuotaUsage[] }>(
    `/v1/teams/${slug}/environments/${tier}/resource-usage`
  );
}

export async function getMetrics(slug: string, tier: string) {
  return get<{ namespace: string; metrics: Record<string, string | null> }>(
    `/v1/teams/${slug}/environments/${tier}/metrics`
  );
}

export async function getDashboards(slug: string, tier: string) {
  return get<{ namespace: string; dashboards: Dashboard[] }>(
    `/v1/teams/${slug}/environments/${tier}/dashboards`
  );
}
