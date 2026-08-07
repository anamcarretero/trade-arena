import {NextResponse, type NextRequest} from "next/server";

export function proxy(request: NextRequest) {
  const locale = request.nextUrl.pathname.split("/")[1];
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-tradearena-locale", locale === "en" ? "en" : "es");
  return NextResponse.next({request: {headers: requestHeaders}});
}

export const config = {
  matcher: ["/es/:path*", "/en/:path*"]
};
