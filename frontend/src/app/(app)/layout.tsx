import { cookies } from "next/headers";
import { AppShell } from "@/components/shell/AppShell";
import { DENSITY_COOKIE, SIDEBAR_COOKIE, THEME_COOKIE } from "@/lib/server/config";
import { requireMe } from "@/lib/server/session";

/**
 * Everything behind the sign-in. Who is signed in is read on the server before anything is drawn, so the sidebar already
 * shows only what this role may open.
 */
export default async function SignedInLayout({ children }: LayoutProps<"/">) {
  const me = await requireMe();
  const jar = await cookies();
  const theme = jar.get(THEME_COOKIE)?.value;
  return (
    <AppShell
      me={me}
      initialCollapsed={jar.get(SIDEBAR_COOKIE)?.value === "collapsed"}
      initialTheme={theme === "light" || theme === "dark" ? theme : "system"}
      initialDensity={jar.get(DENSITY_COOKIE)?.value === "comfortable" ? "comfortable" : "compact"}
    >
      {children}
    </AppShell>
  );
}
