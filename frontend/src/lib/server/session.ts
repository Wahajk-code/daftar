/** Reading the signed-in person on the server, for the first paint. Server components only. */
import { cookies, headers } from "next/headers";
import { cache } from "react";
import { redirect } from "next/navigation";
import type { components } from "@/api/schema";
import { ACCESS_COOKIE, REFRESH_COOKIE, serverConfig } from "./config";

export type Me = components["schemas"]["MeRead"];

/**
 * Who is signed in. If the access cookie has expired but a session exists, the browser is sent through the refresh route
 * and returned here; if there is no session at all it goes to the sign-in screen. Never returns for a signed-out visitor.
 */
export const requireMe = cache(async function requireMe(): Promise<Me> {
  const jar = await cookies();
  const path = (await headers()).get("x-daftar-path") ?? "/";
  const access = jar.get(ACCESS_COOKIE)?.value;

  if (!access) {
    if (jar.has(REFRESH_COOKIE)) redirect(`/api/auth/refresh?next=${encodeURIComponent(path)}`);
    redirect(`/login?next=${encodeURIComponent(path)}`);
  }

  const response = await fetch(`${serverConfig.apiBase}/api/v1/me`, {
    headers: { Authorization: `Bearer ${access}` },
    cache: "no-store",
  });
  if (response.status === 401) redirect(`/api/auth/refresh?next=${encodeURIComponent(path)}`);
  if (!response.ok) throw new Error(`The API answered ${response.status} for /me`);
  return (await response.json()) as Me;
});
