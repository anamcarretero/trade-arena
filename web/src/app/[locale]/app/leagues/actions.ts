"use server";

import {revalidatePath} from "next/cache";
import {redirect} from "next/navigation";
import {apiFetch, type LeagueDetail} from "@/lib/api";
import {isLocale, type Locale} from "@/lib/i18n";
import {invitationPath} from "@/lib/invitations";

function localeFrom(formData: FormData): Locale {
  const locale = String(formData.get("locale") ?? "");
  if (!isLocale(locale)) throw new Error("Unsupported locale");
  return locale;
}

function reference(formData: FormData, name: string) {
  const value = String(formData.get(name) ?? "");
  if (!/^[A-Za-z0-9-]{1,128}$/.test(value)) throw new Error("Invalid reference");
  return value;
}

function signIn(locale: Locale, returnTo: string): never {
  redirect(`/auth/login?locale=${locale}&returnTo=${encodeURIComponent(returnTo)}`);
}

function leaguePath(locale: Locale, leagueId: string) {
  return `/${locale}/app/leagues/${encodeURIComponent(leagueId)}`;
}

export async function createLeague(formData: FormData) {
  const locale = localeFrom(formData);
  const response = await apiFetch("/api/v1/leagues", {
    method: "POST",
    body: JSON.stringify({name: String(formData.get("name") ?? "")})
  });
  if (response.status === 403) signIn(locale, `/${locale}/app`);
  if (response.status === 409) redirect(`/${locale}/app?error=league-limit`);
  if (!response.ok) redirect(`/${locale}/app?error=league-create`);
  const league = await response.json() as LeagueDetail;
  revalidatePath(`/${locale}/app`);
  redirect(leaguePath(locale, league.id));
}

export async function inviteMember(formData: FormData) {
  const locale = localeFrom(formData);
  const leagueId = reference(formData, "league_id");
  const destination = leaguePath(locale, leagueId);
  const response = await apiFetch(`/api/v1/leagues/${leagueId}/invitations`, {
    method: "POST",
    body: JSON.stringify({email: String(formData.get("email") ?? "")})
  });
  if (response.status === 403) signIn(locale, destination);
  if (response.status === 404) redirect(`${destination}?error=access`);
  if (response.status === 409) redirect(`${destination}?error=league-full`);
  if (!response.ok) redirect(`${destination}?error=invite`);
  revalidatePath(destination);
  redirect(`${destination}?status=invited`);
}

export async function revokeInvitation(formData: FormData) {
  const locale = localeFrom(formData);
  const leagueId = reference(formData, "league_id");
  const invitationId = reference(formData, "invitation_id");
  const destination = leaguePath(locale, leagueId);
  const response = await apiFetch(
    `/api/v1/leagues/${leagueId}/invitations/${invitationId}`,
    {method: "DELETE"}
  );
  if (response.status === 403) signIn(locale, destination);
  if (response.status === 404) redirect(`${destination}?error=access`);
  if (!response.ok) redirect(`${destination}?error=revoke`);
  revalidatePath(destination);
  redirect(`${destination}?status=revoked`);
}

export async function removeMember(formData: FormData) {
  const locale = localeFrom(formData);
  const leagueId = reference(formData, "league_id");
  const userId = reference(formData, "user_id");
  const destination = leaguePath(locale, leagueId);
  const response = await apiFetch(
    `/api/v1/leagues/${leagueId}/members/${userId}`,
    {method: "DELETE"}
  );
  if (response.status === 403) signIn(locale, destination);
  if (response.status === 404) redirect(`${destination}?error=access`);
  if (!response.ok) redirect(`${destination}?error=remove`);
  revalidatePath(destination);
  redirect(`${destination}?status=removed`);
}

export async function acceptInvitation(formData: FormData) {
  const locale = localeFrom(formData);
  const invitationId = reference(formData, "invitation_id");
  const invitationPage = invitationPath(locale, invitationId);
  const response = await apiFetch(`/api/v1/invitations/${invitationId}`, {
    method: "POST"
  });
  if (response.status === 403) signIn(locale, invitationPage);
  if (response.status === 404) redirect(`${invitationPage}?error=access`);
  if (response.status === 409) redirect(`${invitationPage}?error=league-full`);
  if (!response.ok) redirect(`${invitationPage}?error=accept`);
  const membership = await response.json() as {league_id: string};
  revalidatePath(`/${locale}/app`);
  redirect(leaguePath(locale, membership.league_id));
}

function competitionDates(formData: FormData) {
  const startsOn = String(formData.get("starts_on") ?? "");
  const endsOn = String(formData.get("ends_on") ?? "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(startsOn) || !/^\d{4}-\d{2}-\d{2}$/.test(endsOn)) {
    throw new Error("Invalid competition calendar");
  }
  return {
    starts_at: `${startsOn}T00:00:00Z`,
    ends_at: `${endsOn}T23:59:59Z`
  };
}

export async function createCompetition(formData: FormData) {
  const locale = localeFrom(formData);
  const leagueId = reference(formData, "league_id");
  const destination = leaguePath(locale, leagueId);
  const response = await apiFetch(`/api/v1/leagues/${leagueId}/competitions`, {
    method: "POST",
    body: JSON.stringify({
      name: String(formData.get("name") ?? ""),
      ...competitionDates(formData)
    })
  });
  if (response.status === 403) signIn(locale, destination);
  if (response.status === 404) redirect(`${destination}?error=access`);
  if (!response.ok) redirect(`${destination}?error=competition`);
  revalidatePath(destination);
  redirect(`${destination}?status=competition-created`);
}

export async function startCompetition(formData: FormData) {
  const locale = localeFrom(formData);
  const leagueId = reference(formData, "league_id");
  const competitionId = reference(formData, "competition_id");
  const destination = leaguePath(locale, leagueId);
  const response = await apiFetch(
    `/api/v1/leagues/${leagueId}/competitions/${competitionId}/start`,
    {method: "POST"}
  );
  if (response.status === 403) signIn(locale, destination);
  if (response.status === 404) redirect(`${destination}?error=access`);
  if (!response.ok) redirect(`${destination}?error=competition`);
  revalidatePath(destination);
  redirect(`${destination}?status=competition-started`);
}

export async function submitOrder(formData: FormData) {
  const locale = localeFrom(formData);
  const leagueId = reference(formData, "league_id");
  const competitionId = reference(formData, "competition_id");
  const destination = leaguePath(locale, leagueId);
  const symbol = String(formData.get("symbol") ?? "").trim().toUpperCase();
  const side = String(formData.get("side") ?? "");
  const orderType = String(formData.get("order_type") ?? "");
  const quantity = Number(formData.get("quantity"));
  const rawLimit = String(formData.get("limit_price") ?? "").trim();
  if (!/^[A-Z][A-Z0-9.-]{0,15}$/.test(symbol) ||
      !["buy", "sell"].includes(side) ||
      !["market", "limit"].includes(orderType) ||
      !Number.isSafeInteger(quantity) || quantity <= 0) {
    redirect(`${destination}?error=order`);
  }
  const response = await apiFetch(
    `/api/v1/leagues/${leagueId}/competitions/${competitionId}/orders`,
    {
      method: "POST",
      body: JSON.stringify({
        symbol, side, quantity, order_type: orderType,
        allow_extended_hours: formData.get("allow_extended_hours") === "on",
        limit_price: orderType === "limit" ? rawLimit : null,
        client_order_id: crypto.randomUUID()
      })
    }
  );
  if (response.status === 403) signIn(locale, destination);
  if (response.status === 404) redirect(`${destination}?error=access`);
  if (!response.ok) redirect(`${destination}?error=order`);
  revalidatePath(destination);
  redirect(`${destination}?status=order-submitted`);
}

export async function cancelOrder(formData: FormData) {
  const locale = localeFrom(formData);
  const leagueId = reference(formData, "league_id");
  const competitionId = reference(formData, "competition_id");
  const orderId = reference(formData, "order_id");
  const destination = leaguePath(locale, leagueId);
  const response = await apiFetch(
    `/api/v1/leagues/${leagueId}/competitions/${competitionId}/orders/${orderId}`,
    {method: "DELETE"}
  );
  if (response.status === 403) signIn(locale, destination);
  if (response.status === 404) redirect(`${destination}?error=access`);
  if (!response.ok) redirect(`${destination}?error=order`);
  revalidatePath(destination);
  redirect(`${destination}?status=order-cancelled`);
}
