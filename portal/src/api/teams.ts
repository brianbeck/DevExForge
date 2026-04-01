import { get, post, patch, del } from "./client";
import type { Team, TeamCreate, TeamUpdate, TeamListResponse } from "@/types";

export function listTeams(
  page: number = 1,
  pageSize: number = 50
): Promise<TeamListResponse> {
  return get<TeamListResponse>(
    `/v1/teams?page=${page}&page_size=${pageSize}`
  );
}

export function getTeam(slug: string): Promise<Team> {
  return get<Team>(`/v1/teams/${slug}`);
}

export function createTeam(data: TeamCreate): Promise<Team> {
  return post<Team>("/v1/teams", data);
}

export function updateTeam(slug: string, data: TeamUpdate): Promise<Team> {
  return patch<Team>(`/v1/teams/${slug}`, data);
}

export function deleteTeam(slug: string): Promise<void> {
  return del(`/v1/teams/${slug}`);
}
