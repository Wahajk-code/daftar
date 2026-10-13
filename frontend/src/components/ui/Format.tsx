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
  return <span className="ident" style={voided ? { textDecoration: "line-through" } : undefined}>{value}</span>;
}

/**
 * The main cell of a row: what it is in bold, and a quieter line under it (the category, the source). Both are cut with an
 * ellipsis when long, and the whole text shows on hover.
 */
export function TwoLine({ title, sub, mono }: { title: string; sub?: string | null; mono?: boolean }) {
  return (
    <span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
      <span className={`clip user-text${mono ? " ident" : ""}`} title={title} style={{ fontWeight: 700, color: "var(--text-1)" }}>
        {title}
      </span>
      {sub ? (
        <span className="clip user-text" title={sub} style={{ fontSize: "var(--text-sm)", color: "var(--text-3)", fontWeight: 400 }}>
          {sub}
        </span>
      ) : null}
    </span>
  );
}
