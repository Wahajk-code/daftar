"use client";

import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useToast } from "@/components/ui/Toast";
import { REFERENCE_STALE_MS } from "@/lib/cache";
import { api, type RequestOptions } from "./client";
import { ApiError, messageFor } from "./errors";
import type { Account, Category, CostCenter, Page, Project, Vendor } from "./types";

type Query = NonNullable<RequestOptions["query"]>;

/** One page of a list. Documents and anything with money are always fetched fresh after a change and on focus. */
export function usePage<T>(path: string, query: Query = {}, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["list", path, query],
    queryFn: ({ signal }) => api<Page<T>>(path, { query, signal }),
    placeholderData: (previous) => previous,
    enabled: options.enabled ?? true,
  });
}

/** One record. */
export function useRecord<T>(key: readonly unknown[], path: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["record", ...key],
    queryFn: ({ signal }) => api<T>(path, { signal }),
    enabled: options.enabled ?? true,
  });
}

/** Every row of a list that is small by nature (cost centres, categories), following the pages. */
export async function fetchAll<T>(path: string, query: Query = {}): Promise<T[]> {
  const rows: T[] = [];
  let offset = 0;
  for (;;) {
    const page = await api<Page<T>>(path, { query: { ...query, limit: 100, offset } });
    rows.push(...page.items);
    offset += page.items.length;
    if (page.items.length === 0 || offset >= page.total) return rows;
  }
}

/**
 * Reference data: the lists a form's drop-downs are made from. Cached for a few minutes, and dropped whenever one of
 * them is changed (see `REFERENCE_ROOT`).
 */
export const REFERENCE_ROOT = "reference";

function useReference<T>(name: string, path: string, query: Query = {}) {
  return useQuery({
    queryKey: [REFERENCE_ROOT, name, query],
    queryFn: () => fetchAll<T>(path, query),
    staleTime: REFERENCE_STALE_MS,
  });
}

export const useCategories = () => useReference<Category>("categories", "/categories", { is_active: true });
export const useCostCenters = () => useReference<CostCenter>("cost-centers", "/cost-centers", { is_active: true });
export const useProjects = () => useReference<Project>("projects", "/projects", { is_active: true });
export const useVendors = () => useReference<Vendor>("vendors", "/vendors", { is_active: true });
/** Names for ids on documents that may point at something since deactivated, so inactive ones are included. */
export const useAllCostCenters = () => useReference<CostCenter>("cost-centers-all", "/cost-centers");
export const useAllProjects = () => useReference<Project>("projects-all", "/projects");
export const useAllAccounts = () => useReference<Account>("accounts-all", "/accounts");
export const useAccounts = () => useReference<Account>("accounts", "/accounts", { is_active: true });

/** What a screen needs to name an id it was given: cost centres and projects by code. */
export function codeMap<T extends { id: number; code: string; name: string }>(rows: T[] | undefined): Map<number, string> {
  return new Map((rows ?? []).map((row) => [row.id, `${row.code} ${row.name}`]));
}

interface ActionOptions<TVars, TResult> {
  mutationFn: (vars: TVars) => Promise<TResult>;
  /** The toast on success, in the same words as the button ("Voucher posted"). */
  success: string | ((result: TResult, vars: TVars) => string);
  /** Query key prefixes to drop so the screen shows what is now true. */
  invalidate?: QueryKey[];
  onSuccess?: (result: TResult, vars: TVars) => void;
}

/**
 * Every change goes through this: the button is disabled while it runs, a toast says what happened, a failure shows the
 * API's own reason with its reference, and the data on screen is fetched again. Nothing is shown as done before the API
 * has said so (never optimistic for post, void or approve).
 */
export function useAction<TVars = void, TResult = unknown>(options: ActionOptions<TVars, TResult>) {
  const client = useQueryClient();
  const toast = useToast();
  return useMutation<TResult, unknown, TVars>({
    mutationFn: options.mutationFn,
    onSuccess: async (result, vars) => {
      const text = typeof options.success === "function" ? options.success(result, vars) : options.success;
      toast.success(text);
      await Promise.all((options.invalidate ?? [["list"], ["record"]]).map((queryKey) => client.invalidateQueries({ queryKey })));
      options.onSuccess?.(result, vars);
    },
    onError: (error) => {
      toast.error(messageFor(error), error instanceof ApiError && error.status >= 500 ? error.correlationId : undefined);
    },
  });
}

/** The whole cache of changed documents: lists, single records and the reports built from them. */
export const DOCUMENT_KEYS: QueryKey[] = [["list"], ["record"], ["history"], ["report"], ["duplicates"]];
