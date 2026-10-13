"use client";

import { IconFileTypeCsv } from "@tabler/icons-react";
import { download } from "@/api/client";
import { useAction } from "@/api/queries";
import { Button } from "./Button";

/**
 * Downloads what the list is showing, with the filters in use, as a CSV file (UTF-8 with a byte-order mark so Excel reads
 * it, plain amounts with a currency column, dates as YYYY-MM-DD, times in UTC). The server limits and records each export.
 */
export function ExportButton({ path, query, label = "Export CSV" }: { path: string; query: Record<string, string | string[] | undefined>; label?: string }) {
  const run = useAction<void, void>({
    mutationFn: () => download(path, Object.fromEntries(Object.entries(query).filter(([, value]) => value !== undefined && value !== ""))),
    success: "Download started",
    invalidate: [],
  });
  return (
    <Button icon={<IconFileTypeCsv size={20} stroke={1.75} aria-hidden />} pending={run.isPending} onClick={() => run.mutate()}>
      {label}
    </Button>
  );
}
