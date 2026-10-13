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

/** A short amount for an axis: 0, 500, 1.5K, 2M. Whole rupees only above a thousand; never rounds up. */
export function compactMoney(paisa: bigint): string {
  const rupees = paisa / BigInt(100);
  const oneDecimal = (value: bigint, unit: bigint) => {
    const tenths = (value * BigInt(10)) / unit;
    const rest = tenths % BigInt(10);
    return `${tenths / BigInt(10)}${rest === ZERO_PAISA ? "" : `.${rest}`}`;
  };
  if (rupees >= BigInt(1_000_000)) return `${oneDecimal(rupees, BigInt(1_000_000))}M`;
  if (rupees >= BigInt(1_000)) return `${oneDecimal(rupees, BigInt(1_000))}K`;
  return paisa % BigInt(100) === ZERO_PAISA ? String(rupees) : fromPaisa(paisa).replace(/0$/, "");
}

/** The next round number (1, 2, 5 times a power of ten rupees) at or above `paisa`: the top of a chart's axis. */
export function niceCeiling(paisa: bigint): bigint {
  const hundred = BigInt(100);
  const rupees = paisa / hundred + (paisa % hundred > ZERO_PAISA ? BigInt(1) : ZERO_PAISA);
  if (rupees <= ZERO_PAISA) return hundred;
  let magnitude = BigInt(1);
  while (magnitude * BigInt(10) <= rupees) magnitude *= BigInt(10);
  for (const step of [BigInt(1), BigInt(2), BigInt(5), BigInt(10)]) {
    if (step * magnitude >= rupees) return step * magnitude * hundred;
  }
  return BigInt(10) * magnitude * hundred;
}

/** What share of `whole` is `part`, as a percentage with two places (for a bar's height or width, never for money). */
export function percentOf(part: bigint, whole: bigint): number {
  if (whole <= ZERO_PAISA || part <= ZERO_PAISA) return 0;
  return Number((part * BigInt(10000)) / whole) / 100;
}

/** The currency every amount in the app is in. Documents carry it too (`currency`), and it is PKR throughout. */
export const CURRENCY = "PKR";

/** Amount text for a sum or a total, with the currency in front: "PKR 1,234.00". */
export function formatWithCurrency(text: string | null | undefined, currency: string = CURRENCY): string {
  const amount = formatMoney(text);
  return amount === "" ? "" : `${currency} ${amount}`;
}
