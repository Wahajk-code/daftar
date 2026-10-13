"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/api/errors";
import { ToastProvider } from "@/components/ui/Toast";

/**
 * Cache policy (docs/decisions.md, decision 39). Reference data (accounts, categories, cost centres, rates) is cached for a
 * few minutes by the hooks that read it and is invalidated when it changes. Everything else, documents, balances and any
 * amount of money, is always refetched after a change and when the window regains focus.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 0,
            refetchOnWindowFocus: true,
            retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}

