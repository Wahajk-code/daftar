import Link from "next/link";
import type { ReactNode } from "react";
import type { Role } from "@/api/types";
import { requireMe } from "@/lib/server/session";

function NoAccess() {
  return (
    <div style={{ maxWidth: 520, display: "flex", flexDirection: "column", gap: "var(--space-3)", paddingTop: "var(--space-6)" }}>
      <h1>Your role does not include this screen</h1>
      <p className="muted">
        The menu shows only what you can open. If you think you should have access, ask an Admin to check your role.
      </p>
      <p>
        <Link href="/">Go to the home screen</Link>
      </p>
    </div>
  );
}

/**
 * Shows a screen only to the roles that may use it, decided on the server before anything is sent. This is courtesy, not
 * security: the API refuses the same calls to anyone else (docs/architecture.md, access matrix).
 */
export async function Gate({ roles, children }: { roles: readonly Role[]; children: ReactNode }) {
  const me = await requireMe();
  return roles.includes(me.role) ? children : <NoAccess />;
}
