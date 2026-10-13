import { NextRequest, NextResponse } from "next/server";
import { REFRESH_COOKIE } from "@/lib/server/config";
import { callApi, clearSession, isSameOrigin, problem, upstreamHeaders } from "@/lib/server/upstream";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) return problem(403, "FORBIDDEN", "This request did not come from the Daftar site.");
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (refresh) {
    // Ending the session at the API is best effort: the cookies are cleared either way.
    await callApi("/auth/logout", {
      method: "POST",
      headers: upstreamHeaders(request, { "Content-Type": "application/json" }),
      body: JSON.stringify({ refresh_token: refresh }),
    }).catch(() => undefined);
  }
  const response = new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
  clearSession(response);
  return response;
}
