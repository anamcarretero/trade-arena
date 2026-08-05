import {NextRequest, NextResponse} from "next/server";
import {isLocale} from "@/lib/i18n";
import {saveLocale} from "@/lib/session";
import {serverConfig} from "@/lib/config";

export async function GET(request: NextRequest) {
  const rawLocale = request.nextUrl.searchParams.get("locale") ?? "";
  const candidate = request.nextUrl.searchParams.get("returnTo") ?? "";
  const locale = isLocale(rawLocale) ? rawLocale : "es";
  const returnTo = candidate.startsWith(`/${locale}`) && !candidate.startsWith("//")
    ? candidate : `/${locale}`;
  await saveLocale(locale);
  return NextResponse.redirect(new URL(returnTo, serverConfig().appBaseUrl));
}
