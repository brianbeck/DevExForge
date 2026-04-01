import { get, post, patch, del } from "./client";
import type {
  Environment,
  EnvironmentCreate,
  EnvironmentUpdate,
} from "@/types";

export function listEnvironments(teamSlug: string): Promise<Environment[]> {
  return get<Environment[]>(`/v1/teams/${teamSlug}/environments`);
}

export function getEnvironment(
  teamSlug: string,
  tier: string
): Promise<Environment> {
  return get<Environment>(`/v1/teams/${teamSlug}/environments/${tier}`);
}

export function createEnvironment(
  teamSlug: string,
  data: EnvironmentCreate
): Promise<Environment> {
  return post<Environment>(`/v1/teams/${teamSlug}/environments`, data);
}

export function updateEnvironment(
  teamSlug: string,
  tier: string,
  data: EnvironmentUpdate
): Promise<Environment> {
  return patch<Environment>(
    `/v1/teams/${teamSlug}/environments/${tier}`,
    data
  );
}

export function deleteEnvironment(
  teamSlug: string,
  tier: string
): Promise<void> {
  return del(`/v1/teams/${teamSlug}/environments/${tier}`);
}
