"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";

/**
 * Which notifications this person has already opened. A notification is a document waiting for them; once they open it, it
 * stops showing on the bell. It is remembered in this browser, per person, and is tied to the document and its status, so
 * the same document coming back (sent back again, sent for approval again) is a new notification.
 */
const LIMIT = 400;
const listeners = new Set<() => void>();

const keyFor = (userId: number) => `daftar_seen_${userId}`;

function read(userId: number): string {
  try {
    return window.localStorage.getItem(keyFor(userId)) ?? "";
  } catch {
    return "";
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** The identity of one notification. */
export const notificationId = (kind: string, id: number, status: string) => `${kind}:${id}:${status}`;

export function useSeen(userId: number) {
  const raw = useSyncExternalStore(subscribe, () => read(userId), () => "");
  const seen = useMemo(() => new Set(raw ? raw.split(",") : []), [raw]);

  const mark = useCallback(
    (ids: string[]) => {
      const current = read(userId);
      const known = new Set(current ? current.split(",") : []);
      if (ids.every((id) => known.has(id))) return;
      const next = [...known, ...ids].slice(-LIMIT).join(",");
      try {
        window.localStorage.setItem(keyFor(userId), next);
      } catch {
        return;
      }
      listeners.forEach((listener) => listener());
    },
    [userId],
  );

  return { seen, mark };
}
