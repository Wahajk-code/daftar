/**
 * Dates and instants (docs/domain-rules.md section 7). One date format and one instant format for the whole app:
 *   date     12 Oct 2026
 *   instant  12 Oct 2026, 14:05   (24-hour, in the display zone from /me, never the browser's)
 * Month names come from this file, not from the browser's locale, so the server render and the browser render are
 * identical whatever the machine or its time zone.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;

/** The zone to show times in until /me has told us: the same default the server uses. */
export const DEFAULT_ZONE = "Asia/Karachi";

const ABBREVIATIONS: Record<string, string> = { "Asia/Karachi": "PKT", UTC: "UTC", "Etc/UTC": "UTC" };

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** A business date ("2026-10-12") as "12 Oct 2026". It carries no time or zone and is never converted. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "";
  const match = DATE_ONLY.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  const name = MONTHS[Number(month) - 1];
  return name ? `${Number(day)} ${name} ${year}` : value;
}

interface Parts {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
}

function partsIn(instant: Date, zone: string): Parts {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: zone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  const found: Record<string, string> = {};
  for (const part of formatter.formatToParts(instant)) found[part.type] = part.value;
  return { year: found.year, month: found.month, day: found.day, hour: found.hour, minute: found.minute };
}

/** An instant (ISO 8601 with Z) as "12 Oct 2026, 14:05" in the given zone. */
export function formatInstant(value: string | null | undefined, zone: string = DEFAULT_ZONE): string {
  if (!value) return "";
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return value;
  const p = partsIn(instant, zone);
  return `${Number(p.day)} ${MONTHS[Number(p.month) - 1]} ${p.year}, ${p.hour}:${p.minute}`;
}

/** The same instant with the zone named, for a tooltip: "12 Oct 2026, 14:05 PKT". */
export function formatInstantLong(value: string | null | undefined, zone: string = DEFAULT_ZONE): string {
  if (!value) return "";
  return `${formatInstant(value, zone)} ${ABBREVIATIONS[zone] ?? zone}`;
}

/** Today's calendar date in the display zone, as YYYY-MM-DD: the default for a new document. */
export function todayInZone(zone: string = DEFAULT_ZONE, now: Date = new Date()): string {
  const p = partsIn(now, zone);
  return `${p.year}-${p.month}-${p.day}`;
}

/** The first day of the month containing `date` (YYYY-MM-DD), for report ranges. */
export function startOfMonth(date: string): string {
  return `${date.slice(0, 8)}01`;
}
