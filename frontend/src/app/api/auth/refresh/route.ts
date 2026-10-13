import { NextRequest, NextResponse } from "next/server";
import { REFRESH_COOKIE } from "@/lib/server/config";
import { clearSession, isSameOrigin, problem, refreshTokens, setSession } from "@/lib/server/upstream";

/** A path inside this site, or "/": never an address on another site. */
function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : "/";
}

/**
 * GET is for a page that found the access cookie gone: it refreshes and sends the browser back to where it was going.
 * It changes only this browser's own cookies, so it needs no origin check; it never reveals a token.
 */
export async function GET(request: NextRequest) {
  const next = safeNext(request.nextUrl.searchParams.get("next"));
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  const pair = refresh ? await refreshTokens(request, refresh) : null;
  if (!pair) {
    const login = new URL("/login", request.nextUrl.origin);
    login.searchParams.set("next", next);
    const response = NextResponse.redirect(login);
    clearSession(response);
    return response;
  }
  const response = NextResponse.redirect(new URL(next, request.nextUrl.origin));
  setSession(response, pair);
  return response;
}

/** POST is for script that wants a fresh session without leaving the page. */
export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) return problem(403, "FORBIDDEN", "This request did not come from the Daftar site.");
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  const pair = refresh ? await refreshTokens(request, refresh) : null;
  if (!pair) {
    const response = problem(401, "UNAUTHENTICATED", "Sign in to continue.");
    clearSession(response);
    return response;
  }
  const response = new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
  setSession(response, pair);
  return response;
}
