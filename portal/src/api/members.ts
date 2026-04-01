import { get, post, patch, del } from "./client";
import type { Member, MemberCreate } from "@/types";

export function listMembers(teamSlug: string): Promise<Member[]> {
  return get<Member[]>(`/v1/teams/${teamSlug}/members`);
}

export function addMember(
  teamSlug: string,
  data: MemberCreate
): Promise<Member> {
  return post<Member>(`/v1/teams/${teamSlug}/members`, data);
}

export function updateMember(
  teamSlug: string,
  memberId: string,
  role: string
): Promise<Member> {
  return patch<Member>(`/v1/teams/${teamSlug}/members/${memberId}`, {
    role,
  });
}

export function removeMember(
  teamSlug: string,
  memberId: string
): Promise<void> {
  return del(`/v1/teams/${teamSlug}/members/${memberId}`);
}

export function transferOwnership(
  teamSlug: string,
  newOwnerEmail: string
): Promise<void> {
  return post<void>(`/v1/teams/${teamSlug}/transfer-ownership`, {
    newOwnerEmail,
  });
}
