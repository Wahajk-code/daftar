"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { Me } from "@/api/types";
import { DEFAULT_ZONE } from "@/lib/dates";

const MeContext = createContext<Me | null>(null);

export function MeProvider({ me, children }: { me: Me; children: ReactNode }) {
  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}

/** The signed-in person. Only used inside the signed-in app. */
export function useMe(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error("useMe is only available inside the signed-in app");
  return me;
}

/** The zone times are shown in: the one /me gave, or the default on screens that have no session. */
export function useZone(): string {
  return useContext(MeContext)?.display_timezone ?? DEFAULT_ZONE;
}
