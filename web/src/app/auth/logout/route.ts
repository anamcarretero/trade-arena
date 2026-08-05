import {NextResponse} from "next/server";
import {apiFetch} from "@/lib/api";
import {clearSession} from "@/lib/session";
import {serverConfig} from "@/lib/config";

export async function POST() {
  await apiFetch("/api/v1/auth/logout", {method: "POST"}).catch(() => null);
  await clearSession();
  const config = serverConfig();
  const logout = new URL(`https://${config.auth0Domain}/v2/logout`);
  logout.search = new URLSearchParams({client_id: config.auth0ClientId, returnTo: `${config.appBaseUrl}/`}).toString();
  return NextResponse.redirect(logout, 303);
}
