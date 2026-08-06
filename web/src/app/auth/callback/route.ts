import {NextRequest, NextResponse} from "next/server";
import {serverConfig} from "@/lib/config";
import {consumeTransaction, saveSession} from "@/lib/session";

export async function GET(request: NextRequest) {
  const config = serverConfig();
  const transaction = await consumeTransaction();
  const state = request.nextUrl.searchParams.get("state");
  const code = request.nextUrl.searchParams.get("code");
  const fallbackLocale = transaction?.locale ?? "es";
  const fail = () => NextResponse.redirect(
    new URL(`/${fallbackLocale}?auth_error=1`, config.appBaseUrl)
  );
  if (!transaction || !code || state !== transaction.state || request.nextUrl.searchParams.has("error")) return fail();
  try {
    const tokenResponse = await fetch(`https://${config.auth0Domain}/oauth/token`, {
      method: "POST",
      headers: {"Content-Type": "application/x-www-form-urlencoded"},
      body: new URLSearchParams({
        grant_type: "authorization_code",
        client_id: config.auth0ClientId,
        client_secret: config.auth0ClientSecret,
        redirect_uri: `${config.appBaseUrl}/auth/callback`,
        code,
        code_verifier: transaction.codeVerifier
      }),
      cache: "no-store"
    });
    if (!tokenResponse.ok) return fail();
    const tokens = await tokenResponse.json() as {id_token?: string};
    if (!tokens.id_token) return fail();
    const exchange = await fetch(`${config.apiBaseUrl}/api/v1/auth/session`, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-TradeArena-BFF": config.bffSharedSecret},
      body: JSON.stringify({id_token: tokens.id_token, nonce: transaction.nonce}),
      cache: "no-store"
    });
    if (!exchange.ok) return fail();
    const session = await exchange.json() as {session_token: string; expires_in: number};
    await saveSession(session.session_token, session.expires_in);
    return NextResponse.redirect(new URL(transaction.returnTo, config.appBaseUrl));
  } catch {
    return fail();
  }
}
