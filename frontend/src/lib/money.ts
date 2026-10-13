/**
 * Money on the client. Amounts travel as strings with two places ("1500.00") and are never converted to a floating point
 * number: sums and comparisons are done in whole paisa as BigInt, and text is built by hand. This is the only module that
 * does arithmetic on amounts, as on the server.
 */

export const ZERO_PAISA = BigInt(0);

const AMOUNT = /^-?\d{1,12}(\.\d{1,2})?$/;

/** True for text that is an amount with at most two decimal places and no thousands separators. */
export function isAmount(text: string): boolean {
  return AMOUNT.test(text.trim());
}

/** Whole paisa from amount text, or null when it is not an amount. "12.5" is 1250 paisa. */
export function toPaisa(text: string): bigint | null {
  const clean = stripSeparators(text);
  if (!isAmount(clean)) return null;
  const negative = clean.startsWith("-");
  const [whole, fraction = ""] = clean.replace("-", "").split(".");
  const paisa = BigInt(whole + fraction.padEnd(2, "0"));
  return negative ? -paisa : paisa;
}

/** Amount text with two places from whole paisa: 123456 is "1234.56". */
export function fromPaisa(paisa: bigint): string {
  const negative = paisa < ZERO_PAISA;
  const digits = (negative ? -paisa : paisa).toString().padStart(3, "0");
  const text = `${digits.slice(0, -2)}.${digits.slice(-2)}`;
  return negative ? `-${text}` : text;
}

/** What a person types may carry commas and spaces; the value does not. */
export function stripSeparators(text: string): string {
  return text.replace(/[,\s]/g, "");
}

/** Amount text for display: thousands separators, two places. "1500" and "1500.5" both read well. */
export function formatMoney(text: string | null | undefined): string {
  if (text === null || text === undefined || text === "") return "";
  const paisa = toPaisa(text);
  if (paisa === null) return text;
  const plain = fromPaisa(paisa);
  const negative = plain.startsWith("-");
  const [whole, fraction] = plain.replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}${grouped}.${fraction}`;
}

/** The sum of amount texts, as amount text. Anything that is not an amount counts as zero. */
export function sumAmounts(values: ReadonlyArray<string | null | undefined>): string {
  let total = ZERO_PAISA;
  for (const value of values) total += toPaisa(value ?? "") ?? ZERO_PAISA;
  return fromPaisa(total);
}

/** a minus b, as amount text. */
export function subtractAmounts(a: string, b: string): string {
  return fromPaisa((toPaisa(a) ?? ZERO_PAISA) - (toPaisa(b) ?? ZERO_PAISA));
}

/** True when the amount text is more than zero. */
export function isPositive(text: string | null | undefined): boolean {
  const paisa = toPaisa(text ?? "");
  return paisa !== null && paisa > ZERO_PAISA;
}

/** Basis points as a percentage for display: 3333 is "33.33%", 1800 is "18%". */
export function formatBasisPoints(bp: number): string {
  const whole = Math.trunc(bp / 100);
  const rest = String(bp % 100).padStart(2, "0").replace(/0$/, "");
  return rest === "" || rest === "0" ? `${whole}%` : `${whole}.${rest}%`;
}

/** A percentage typed by a person ("33.33", "18") as whole basis points (3333, 1800), or null if it is not 0 to 100. */
export function percentToBp(text: string): number | null {
  const paisa = toPaisa(stripSeparators(text) || "0");
  return paisa === null || paisa < ZERO_PAISA || paisa > BigInt(10000) ? null : Number(paisa);
}

/** Basis points as the text a person types: 3333 is "33.33", 1800 is "18". */
export function bpToPercent(bp: number): string {
  const whole = Math.floor(bp / 100);
  const rest = bp % 100;
  return rest === 0 ? String(whole) : `${whole}.${String(rest).padStart(2, "0").replace(/0$/, "")}`;
}
