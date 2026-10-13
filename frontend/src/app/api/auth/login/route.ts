import { NextRequest, NextResponse } from "next/server";
import { callApi, isSameOrigin, problem, setSession, upstreamHeaders, type TokenPair } from "@/lib/server/upstream";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) return problem(403, "FORBIDDEN", "This request did not come from the Daftar site.");
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return problem(400, "BAD_REQUEST", "Send the email and password as JSON.");
  }
  const upstream = await callApi("/auth/login", {
    method: "POST",
    headers: upstreamHeaders(request, { "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!upstream.ok) {
    const headers = new Headers({ "Cache-Control": "no-store" });
    const wait = upstream.headers.get("retry-after");
    if (wait) headers.set("Retry-After", wait);
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: { ...Object.fromEntries(headers), "Content-Type": "application/json" },
    });
  }
  const pair = (await upstream.json()) as TokenPair;
  // The tokens go into HttpOnly cookies. The page gets only who signed in.
  const response = NextResponse.json({ user: pair.user }, { headers: { "Cache-Control": "no-store" } });
  setSession(response, pair);
  return response;
}
