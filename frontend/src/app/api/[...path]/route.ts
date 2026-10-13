/**
 * The one proxy between the browser and the API: /api/<anything> becomes /api/v1/<anything>. It adds the access token from
 * the HttpOnly cookie, refreshes once on a 401, checks the origin of anything that changes data, and hands the answer back
 * as it came (status, body, and the few headers a screen needs).
 */
import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/server/config";
import {
  MUTATING,
  callApi,
  clearSession,
  isSameOrigin,
  problem,
  refreshTokens,
  setSession,
  upstreamHeaders,
  type TokenPair,
} from "@/lib/server/upstream";

const FORWARDED_REQUEST_HEADERS = ["content-type", "accept", "if-match", "idempotency-key"];
const FORWARDED_RESPONSE_HEADERS = [
  "content-type",
  "content-disposition",
  "retry-after",
  "x-correlation-id",
  "etag",
  "content-length",
];

type Context = { params: Promise<{ path: string[] }> };

async function send(request: NextRequest, path: string, body: ArrayBuffer | undefined, access: string | undefined) {
  const headers = upstreamHeaders(request);
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const query = request.nextUrl.search;
  return callApi(`/${path}${query}`, { method: request.method, headers, body });
}

async function handle(request: NextRequest, context: Context): Promise<NextResponse> {
  if (MUTATING.has(request.method) && !isSameOrigin(request)) {
    return problem(403, "FORBIDDEN", "This request did not come from the Daftar site.");
  }
  const { path } = await context.params;
  const target = path.map(encodeURIComponent).join("/");
  const body = MUTATING.has(request.method) ? await request.arrayBuffer() : undefined;

  let access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  let renewed: TokenPair | null = null;

  // The access cookie lives as long as the token does; when it is gone, renew before asking.
  if (!access && refresh) {
    renewed = await refreshTokens(request, refresh);
    access = renewed?.access_token;
  }

  let upstream = await send(request, target, body, access);
  if (upstream.status === 401 && refresh && !renewed) {
    renewed = await refreshTokens(request, refresh);
    if (renewed) upstream = await send(request, target, body, renewed.access_token);
  }

  const headers = new Headers({ "Cache-Control": "no-store" });
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  const response = new NextResponse(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers,
  });
  if (renewed) setSession(response, renewed);
  if (upstream.status === 401 && refresh && !renewed) clearSession(response);
  return response;
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
