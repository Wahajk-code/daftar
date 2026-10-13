"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/**
 * Filters, sort and page live in the address bar, so a list can be bookmarked, shared and reached with the back button.
 * `set` changes some values and keeps the rest; a null or empty value removes the parameter. Changing anything but the
 * page returns to the first page.
 */
export function useUrlState() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const set = useCallback(
    (patch: Record<string, string | number | null | undefined>) => {
      const next = new URLSearchParams(params.toString());
      let touchedFilter = false;
      for (const [key, value] of Object.entries(patch)) {
        if (value === null || value === undefined || value === "") next.delete(key);
        else next.set(key, String(value));
        if (key !== "offset") touchedFilter = true;
      }
      if (touchedFilter && !("offset" in patch)) next.delete("offset");
      const text = next.toString();
      router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  /** A filter that holds several values (statuses): the parameter is repeated, one per value. */
  const setList = useCallback(
    (key: string, values: string[]) => {
      const next = new URLSearchParams(params.toString());
      next.delete(key);
      values.forEach((value) => next.append(key, value));
      next.delete("offset");
      const text = next.toString();
      router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const get = useCallback((key: string) => params.get(key) ?? "", [params]);
  const clear = useCallback(
    (keys: string[]) => {
      const next = new URLSearchParams(params.toString());
      keys.forEach((key) => next.delete(key));
      next.delete("offset");
      const text = next.toString();
      router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return useMemo(() => ({ params, get, set, setList, clear }), [params, get, set, setList, clear]);
}

export const PAGE_SIZE = 25;
