import { NextRequest, NextResponse } from "next/server";
import { REFRESH_COOKIE } from "@/lib/server/config";

/** The four screens anyone can open. Everything else needs a session. */
const PUBLIC_PAGES = ["/login", "/forgot-password", "/reset-password", "/accept-invite"];
/** Signed-in people have no use for these two, so they are sent home. The reset and invite links must keep working. */
const SIGNED_OUT_ONLY = ["/login", "/forgot-password"];

const matches = (pathname: string, pages: string[]) => pages.some((page) => pathname === page || pathname.startsWith(`${page}/`));

/**
 * An early, optimistic check: no session cookie, no private page. Real authorisation happens at the API on every call;
 * this only saves a signed-out visitor from a screen that cannot load.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const signedIn = request.cookies.has(REFRESH_COOKIE);

  if (!signedIn && !matches(pathname, PUBLIC_PAGES)) {
    const login = new URL("/login", request.url);
    if (pathname !== "/") login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }
  if (signedIn && matches(pathname, SIGNED_OUT_ONLY)) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // Server components cannot see the URL, so the path travels as a request header (used to come back after a refresh).
  const headers = new Headers(request.headers);
  headers.set("x-daftar-path", `${pathname}${search}`);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|robots.txt|manifest.webmanifest|pwa-icons).*)"],
};
