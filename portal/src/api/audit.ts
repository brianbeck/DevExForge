import { get } from "./client";

export interface AuditEntry {
  id: number;
  timestamp: string;
  userEmail: string;
  action: string;
  resourceType: string;
  resourceId: string | null;
  teamSlug: string | null;
  requestBody: Record<string, unknown> | null;
  responseStatus: number | null;
}

export interface AuditLogList {
  entries: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

export async function getAuditLog(params?: {
  teamSlug?: string;
  userEmail?: string;
  action?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditLogList> {
  const searchParams = new URLSearchParams();
  if (params?.teamSlug) searchParams.set("team_slug", params.teamSlug);
  if (params?.userEmail) searchParams.set("user_email", params.userEmail);
  if (params?.action) searchParams.set("action", params.action);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return get<AuditLogList>(`/v1/audit${qs ? `?${qs}` : ""}`);
}

export async function getTeamAuditLog(slug: string, params?: {
  limit?: number;
  offset?: number;
}): Promise<AuditLogList> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return get<AuditLogList>(`/v1/teams/${slug}/audit${qs ? `?${qs}` : ""}`);
}
