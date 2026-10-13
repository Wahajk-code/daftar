import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import type { Role } from "@/api/types";
import { requireMe } from "@/lib/server/session";

/**
 * Lets a screen through only to the roles that may use it, decided on the server before anything of it is sent. Anyone else
 * is sent to their home screen: they never see the screen, and never a message about it. This is courtesy, not security: the
 * API refuses the same calls to anyone else (docs/architecture.md, access matrix).
 */
export async function Gate({ roles, children }: { roles: readonly Role[]; children: ReactNode }) {
  const me = await requireMe();
  if (!roles.includes(me.role)) redirect("/");
  return children;
}
