import type {components, paths} from "./api-schema";
import {readSessionToken} from "./session";
import {serverConfig} from "./config";

export type ApiPath = keyof paths;
export type ApiRoute = ApiPath
  | `/api/v1/leagues/${string}`
  | `/api/v1/leagues/${string}/invitations`
  | `/api/v1/leagues/${string}/invitations/${string}`
  | `/api/v1/leagues/${string}/members/${string}`
  | `/api/v1/leagues/${string}/competitions`
  | `/api/v1/leagues/${string}/competitions/${string}`
  | `/api/v1/leagues/${string}/competitions/${string}/start`
  | `/api/v1/leagues/${string}/competitions/${string}/portfolio`
  | `/api/v1/leagues/${string}/competitions/${string}/orders`
  | `/api/v1/leagues/${string}/competitions/${string}/orders/${string}`
  | `/api/v1/leagues/${string}/competitions/${string}/ranking`
  | `/api/v1/invitations/${string}`;
export type OwnAccount = {
  user: {id: string; email: string};
  profile: null | {display_name: string; locale: "es" | "en"; birth_date: string};
};
export type LeagueDetail = components["schemas"]["LeagueDetail"];
export type OwnInvitation = components["schemas"]["OwnInvitation"];
export type Competition = components["schemas"]["Competition"];
export type Portfolio = components["schemas"]["Portfolio"];
export type Ranking = components["schemas"]["Ranking"];

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

export async function leagueCompetitions(leagueId: string): Promise<Competition[] | null> {
  const response = await apiFetch(
    `/api/v1/leagues/${encodeURIComponent(leagueId)}/competitions`
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`TradeArena API returned ${response.status}`);
  return response.json();
}

export async function competitionPortfolio(
  leagueId: string, competitionId: string
): Promise<Portfolio | null> {
  const response = await apiFetch(
    `/api/v1/leagues/${encodeURIComponent(leagueId)}/competitions/${encodeURIComponent(competitionId)}/portfolio`
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`TradeArena API returned ${response.status}`);
  return response.json();
}

export async function competitionRanking(
  leagueId: string, competitionId: string
): Promise<Ranking | null> {
  const response = await apiFetch(
    `/api/v1/leagues/${encodeURIComponent(leagueId)}/competitions/${encodeURIComponent(competitionId)}/ranking`
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`TradeArena API returned ${response.status}`);
  return response.json();
}
