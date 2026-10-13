"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Counts down the wait a 429 asks for (its Retry-After), so a button can say "Try again in 38 seconds" and come back by
 * itself. `start(seconds)` begins a wait; `remaining` is 0 when there is none.
 */
export function useCooldown() {
  const [until, setUntil] = useState(0);
  const [now, setNow] = useState(0);

  useEffect(() => {
    if (until === 0) return;
    const timer = window.setInterval(() => {
      setNow(Date.now());
      if (Date.now() >= until) window.clearInterval(timer);
    }, 500);
    return () => window.clearInterval(timer);
  }, [until]);

  const start = useCallback((seconds: number) => {
    const moment = Date.now();
    setNow(moment);
    setUntil(moment + seconds * 1000);
  }, []);

  const remaining = until === 0 ? 0 : Math.max(0, Math.ceil((until - now) / 1000));
  return { remaining, start };
}
