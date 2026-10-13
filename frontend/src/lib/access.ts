import type { Role } from "@/api/types";

const EVERYONE: readonly Role[] = ["admin", "accountant", "approver", "staff"];
const OFFICE: readonly Role[] = ["admin", "accountant", "approver"];
const BOOKKEEPERS: readonly Role[] = ["admin", "accountant"];

/**
 * Who may open each screen, most specific first. The signed-in layout checks this before anything is drawn, so a person who
 * types an address they may not use is sent home instead of seeing the screen or a message about it. Courtesy, not security:
 * the API refuses the same calls (the access matrix test is the real boundary).
 */
const RULES: Array<[RegExp, readonly Role[]]> = [
  [/^\/expenses\/(new|\d+\/edit)$/, ["admin", "accountant", "staff"]],
  [/^\/(purchases|vouchers)\/(new|\d+\/edit)$/, BOOKKEEPERS],
  [/^\/expenses(\/|$)/, EVERYONE],
  [/^\/(purchases|vouchers|reports|vendors|accounts|categories|cost-centers|projects|tax-rules|periods|settings)(\/|$)/, OFFICE],
  [/^\/approvals(\/|$)/, ["admin", "approver"]],
  [/^\/(users|audit)(\/|$)/, ["admin"]],
];

/** The roles allowed on a path, or null when the path is open to everyone signed in. */
export function rolesFor(pathname: string): readonly Role[] | null {
  return RULES.find(([pattern]) => pattern.test(pathname))?.[1] ?? null;
}
