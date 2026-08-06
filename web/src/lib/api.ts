import type {components, paths} from "./api-schema";
import {readSessionToken} from "./session";
import {serverConfig} from "./config";

export type ApiPath = keyof paths;
export type ApiRoute = ApiPath
  | `/api/v1/leagues/${string}`
  | `/api/v1/leagues/${string}/invitations`
  | `/api/v1/leagues/${string}/invitations/${string}`
  | `/api/v1/leagues/${string}/members/${string}`
  | `/api/v1/invitations/${string}`;
export type OwnAccount = {
  user: {id: string; email: string};
  profile: null | {display_name: string; locale: "es" | "en"; birth_date: string};
};
export type LeagueDetail = components["schemas"]["LeagueDetail"];
export type OwnInvitation = components["schemas"]["OwnInvitation"];

export async function apiFetch(path: ApiRoute, init: RequestInit = {}) {
  const token = await readSessionToken();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${serverConfig().apiBaseUrl}${path}`, {...init, headers, cache: "no-store"});
}

export async function ownAccount(): Promise<OwnAccount | null> {
  const response = await apiFetch("/api/v1/me");
  if (response.status === 403) return null;
  if (!response.ok) throw new Error(`TradeArena API returned ${response.status}`);
  return response.json();
}

export async function ownLeagues(): Promise<LeagueDetail[] | null> {
  const response = await apiFetch("/api/v1/leagues");
  if (response.status === 403) return null;
  if (!response.ok) throw new Error(`TradeArena API returned ${response.status}`);
  return response.json();
}

export async function leagueDetail(leagueId: string): Promise<LeagueDetail | null> {
  const response = await apiFetch(`/api/v1/leagues/${encodeURIComponent(leagueId)}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`TradeArena API returned ${response.status}`);
  return response.json();
}

export async function ownInvitations(): Promise<OwnInvitation[] | null> {
  const response = await apiFetch("/api/v1/invitations");
  if (response.status === 403) return null;
  if (!response.ok) throw new Error(`TradeArena API returned ${response.status}`);
  return response.json();
}
