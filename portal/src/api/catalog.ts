import { get, post, del } from "./client";

export interface CatalogTemplate {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  chartRepo: string | null;
  chartName: string | null;
  chartVersion: string | null;
  defaultValues: Record<string, unknown> | null;
  valuesSchema: Record<string, unknown> | null;
  createdAt: string;
}

export async function listTemplates(): Promise<CatalogTemplate[]> {
  return get<CatalogTemplate[]>("/api/v1/catalog/templates");
}

export async function getTemplate(id: string): Promise<CatalogTemplate> {
  return get<CatalogTemplate>(`/api/v1/catalog/templates/${id}`);
}

export async function createTemplate(data: Partial<CatalogTemplate>): Promise<CatalogTemplate> {
  return post<CatalogTemplate>("/api/v1/catalog/templates", data);
}

export async function deleteTemplate(id: string): Promise<void> {
  return del(`/api/v1/catalog/templates/${id}`);
}

export async function deployFromTemplate(
  slug: string,
  tier: string,
  data: { templateId: string; appName: string; values?: Record<string, unknown> }
): Promise<{ message: string; applicationName: string; namespace: string; templateName: string }> {
  return post(`/api/v1/teams/${slug}/environments/${tier}/deploy`, data);
}
