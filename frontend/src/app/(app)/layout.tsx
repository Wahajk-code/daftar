import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/shell/AppShell";
import { SIDEBAR_COOKIE } from "@/lib/server/config";
import { rolesFor } from "@/lib/access";
import { requireMe } from "@/lib/server/session";

/**
 * Everything behind the sign-in. Who is signed in is read on the server before anything is drawn, so the sidebar already
 * shows only what this role may open.
 */
export default async function SignedInLayout({ children }: LayoutProps<"/">) {
  const me = await requireMe();
  // Decided here, before any of the screen is sent: a role that may not use the address goes home, and never sees the screen.
  const path = ((await headers()).get("x-daftar-path") ?? "/").split("?")[0];
  const allowed = rolesFor(path);
  if (allowed && !allowed.includes(me.role)) redirect("/");
  const jar = await cookies();
  return (
    <AppShell me={me} initialCollapsed={jar.get(SIDEBAR_COOKIE)?.value === "collapsed"}>
      {children}
    </AppShell>
  );
}
