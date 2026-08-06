import type {paths} from "./api-schema";
import {readSessionToken} from "./session";
import {serverConfig} from "./config";

export type ApiPath = keyof paths;
export type OwnAccount = {
  user: {email: string};
  profile: null | {display_name: string; locale: "es" | "en"; birth_date: string};
};

export async function apiFetch(path: ApiPath, init: RequestInit = {}) {
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
