import { get } from "./client";

export interface Violation {
  constraintKind: string;
  constraintName: string;
  message: string;
  enforcementAction: string;
  resource: { kind: string; namespace: string; name: string };
}

export interface VulnerabilityReport {
  name: string;
  image: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  scanner: string;
  updatedAt: string;
}

export interface SecurityEvent {
  timestamp: string;
  message: string;
  severity: string;
  source: string;
  involvedObject: { kind: string; name: string };
  count: number;
}

export interface ComplianceSummary {
  score: number;
  status: string;
  policyViolations: number;
  criticalCVEs: number;
  highCVEs: number;
  securityEvents: number;
  imageCount: number;
}

export async function getViolations(slug: string, tier: string) {
  return get<{ violations: Violation[]; total: number }>(
    `/v1/teams/${slug}/environments/${tier}/violations`
  );
}

export async function getVulnerabilities(slug: string, tier: string) {
  return get<{ vulnerabilities: VulnerabilityReport[]; total: number }>(
    `/v1/teams/${slug}/environments/${tier}/vulnerabilities`
  );
}

export async function getSecurityEvents(slug: string, tier: string) {
  return get<{ events: SecurityEvent[]; total: number }>(
    `/v1/teams/${slug}/environments/${tier}/security-events`
  );
}

export async function getComplianceSummary(slug: string, tier: string) {
  return get<ComplianceSummary>(
    `/v1/teams/${slug}/environments/${tier}/compliance-summary`
  );
}
