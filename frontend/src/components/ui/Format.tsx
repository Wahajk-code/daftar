"use client";

import { formatDate, formatInstant, formatInstantLong } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { useZone } from "@/components/shell/MeContext";

/** An amount: thousands separators, two places, right aligned, figures that line up. */
export function Money({ value, strong, className }: { value: string | null | undefined; strong?: boolean; className?: string }) {
  return (
    <span className={`num ${className ?? ""}`} style={strong ? { fontWeight: 600 } : undefined}>
      {formatMoney(value)}
    </span>
  );
}

/** A business date, as "12 Oct 2026". Never converted through a zone. */
export function DateText({ value }: { value: string | null | undefined }) {
  return <time dateTime={value ?? undefined}>{formatDate(value)}</time>;
}

/** A moment in time, in the display zone from /me, with the full stamp on hover. */
export function Instant({ value }: { value: string | null | undefined }) {
  const zone = useZone();
  return (
    <time dateTime={value ?? undefined} title={formatInstantLong(value, zone)}>
      {formatInstant(value, zone)}
    </time>
  );
}

/** A voucher, invoice or document number in the identifier face. A void number is struck through. */
export function Identifier({ value, voided }: { value: string | null | undefined; voided?: boolean }) {
  if (!value) return <span className="faint">Not numbered</span>;
  return <span className="mono" style={voided ? { textDecoration: "line-through" } : undefined}>{value}</span>;
}
