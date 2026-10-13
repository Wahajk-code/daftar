"use client";

import { IconPrinter } from "@tabler/icons-react";
import { useMe, useZone } from "@/components/shell/MeContext";
import { formatDate, todayInZone } from "@/lib/dates";
import { Button } from "./Button";

/** Opens the browser's print dialog. What is printed is decided by the print stylesheet: only the page's own data. */
export function PrintButton({ label = "Print" }: { label?: string }) {
  return (
    <Button icon={<IconPrinter size={20} stroke={1.75} aria-hidden />} onClick={() => window.print()}>
      {label}
    </Button>
  );
}

/** A line that appears only on paper: who printed it and when, so a copy can be traced. */
export function PrintStamp() {
  const me = useMe();
  const zone = useZone();
  return (
    <p className="print-only">
      Daftar. Printed {formatDate(todayInZone(zone))} by {me.full_name}.
    </p>
  );
}
