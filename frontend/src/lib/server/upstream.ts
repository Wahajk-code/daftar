/**
 * Talking to the API on behalf of the browser. This is the only place a token is handled: it comes from an HttpOnly
 * cookie, goes out in an Authorization header, and never reaches page script.
 */
import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE,
  BFF_CLIENT_IP_HEADER,
  BFF_SECRET_HEADER,
  REFRESH_COOKIE,
  REFRESH_MAX_AGE_SECONDS,
  serverConfig,
} from "./config";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: { id: number; email: string; full_name: string; role: string };
}

/** The error shape the API uses, so a failure of the web server reads the same as a failure of the API. */
export function problem(status: number, code: string, detail: string, headers?: HeadersInit): NextResponse {
  return NextResponse.json(
    { type: `urn:daftar:error:${code}`, title: detail, status, detail, code, correlation_id: "", errors: [] },
    { status, headers: { "Cache-Control": "no-store", ...headers } },
  );
}

/** The caller's address, for the API's rate limits. Only believed there because of the shared secret. */
export function clientIp(request: NextRequest): string | null {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const candidate = forwarded || request.headers.get("x-real-ip") || "";
  return candidate || null;
}

export function upstreamHeaders(request: NextRequest, extra: Record<string, string> = {}): Headers {
  const headers = new Headers(extra);
  if (serverConfig.bffSecret) {
    headers.set(BFF_SECRET_HEADER, serverConfig.bffSecret);
    const ip = clientIp(request);
    if (ip) headers.set(BFF_CLIENT_IP_HEADER, ip);
  }
  return headers;
}

export async function callApi(path: string, init: RequestInit & { headers: Headers }): Promise<Response> {
  return fetch(`${serverConfig.apiBase}/api/v1${path}`, { ...init, cache: "no-store", redirect: "manual" });
}

// Refresh tokens rotate: using one spends it, and using a spent one ends every session. Several requests can find the
// access cookie gone at the same moment, so they share one refresh, and a request that was already in flight with the
// old token is handed the same new pair for a short while instead of tripping the theft alarm.
const inFlight = new Map<string, Promise<TokenPair | null>>();
const recent = new Map<string, { pair: TokenPair; at: number }>();
const GRACE_MS = 60_000;

export async function refreshTokens(request: NextRequest, refreshToken: string): Promise<TokenPair | null> {
  const now = Date.now();
  for (const [token, entry] of recent) if (now - entry.at > GRACE_MS) recent.delete(token);
  const done = recent.get(refreshToken);
  if (done) return done.pair;
  const running = inFlight.get(refreshToken);
  if (running) return running;

  const attempt = (async () => {
    const response = await callApi("/auth/refresh", {
      method: "POST",
      headers: upstreamHeaders(request, { "Content-Type": "application/json" }),
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return null;
    const pair = (await response.json()) as TokenPair;
    recent.set(refreshToken, { pair, at: Date.now() });
    return pair;
  })().finally(() => inFlight.delete(refreshToken));
  inFlight.set(refreshToken, attempt);
  return attempt;
}

export function setSession(response: NextResponse, pair: TokenPair): void {
  const base = { httpOnly: true, sameSite: "strict" as const, secure: serverConfig.secureCookies, path: "/" };
  response.cookies.set(ACCESS_COOKIE, pair.access_token, { ...base, maxAge: pair.expires_in });
  response.cookies.set(REFRESH_COOKIE, pair.refresh_token, { ...base, maxAge: REFRESH_MAX_AGE_SECONDS });
}

export function clearSession(response: NextResponse): void {
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE]) response.cookies.set(name, "", { path: "/", maxAge: 0 });
}

/**
 * A request that changes something must come from this site: the browser names its origin, and it must be ours. Together
 * with SameSite=Strict cookies, this is the protection against a page on another site making a signed-in user act.
 */
export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  try {
    return host !== null && new URL(origin).host === host;
  } catch {
    return false;
  }
}

export const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);
