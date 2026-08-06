import {createHash, randomBytes} from "node:crypto";
import {NextRequest, NextResponse} from "next/server";
import {serverConfig} from "@/lib/config";
import {saveLocale, saveTransaction} from "@/lib/session";
import {isLocale} from "@/lib/i18n";

function base64url(value: Buffer) { return value.toString("base64url"); }

export async function GET(request: NextRequest) {
  const requestedLocale = request.nextUrl.searchParams.get("locale") ?? "es";
  const locale = isLocale(requestedLocale) ? requestedLocale : "es";
  const candidate = request.nextUrl.searchParams.get("returnTo") ?? `/${locale}/app`;
  const returnTo = candidate.startsWith(`/${locale}/`) && !candidate.startsWith("//") ? candidate : `/${locale}/app`;
  const state = base64url(randomBytes(32));
  const nonce = base64url(randomBytes(32));
  const codeVerifier = base64url(randomBytes(64));
  const codeChallenge = createHash("sha256").update(codeVerifier).digest("base64url");
  await saveLocale(locale);
  await saveTransaction({state, nonce, codeVerifier, returnTo, locale});
  const config = serverConfig();
  const authorize = new URL(`https://${config.auth0Domain}/authorize`);
  authorize.search = new URLSearchParams({
    response_type: "code",
    client_id: config.auth0ClientId,
    redirect_uri: `${config.appBaseUrl}/auth/callback`,
    scope: "openid profile email",
    state,
    nonce,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
    ui_locales: locale
  }).toString();
  return NextResponse.redirect(authorize);
}
