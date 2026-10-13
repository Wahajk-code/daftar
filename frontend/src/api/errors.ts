import type { ErrorCode, FieldProblem, Problem } from "./types";

/** A failed call, with everything a screen needs to explain it. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode | "NETWORK";
  readonly detail: string;
  readonly fields: FieldProblem[];
  /** Seconds to wait, from the Retry-After header of a 429. */
  readonly retryAfter: number | null;
  readonly correlationId: string;

  constructor(status: number, problem: Partial<Problem> | null, retryAfter: number | null) {
    const code = (problem?.code ?? (status === 0 ? "NETWORK" : "INTERNAL_ERROR")) as ErrorCode | "NETWORK";
    super(problem?.detail ?? code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = problem?.detail ?? "";
    this.fields = problem?.errors ?? [];
    this.retryAfter = retryAfter;
    this.correlationId = problem?.correlation_id ?? "";
  }

  /** The message for this field, if the server named one. */
  fieldMessage(field: string): string | undefined {
    return this.fields.find((problem) => problem.field === field || problem.field.endsWith(`.${field}`))?.message;
  }
}

/**
 * What to say for each error code when the server's own sentence is not the right one to show. A Record over every code:
 * the type checker fails the build if the API gains a code that has no entry here.
 */
const DEFAULT_MESSAGES: Record<ErrorCode, string> = {
  BAD_REQUEST: "That request could not be understood. Check it and try again.",
  VALIDATION_ERROR: "Some fields need attention. Check the highlighted fields.",
  UNAUTHENTICATED: "Your session has ended. Sign in again.",
  FORBIDDEN: "You do not have access to do that.",
  NOT_FOUND: "That record does not exist, or you cannot see it.",
  METHOD_NOT_ALLOWED: "That action is not available here.",
  PAYLOAD_TOO_LARGE: "That file is too large.",
  RATE_LIMITED: "Too many attempts. Wait a moment, then try again.",
  CONFLICT: "That conflicts with something already saved.",
  VERSION_CONFLICT: "Someone else changed this record. Reload it and try again.",
  INVALID_CREDENTIALS: "The email or password is not right.",
  REAUTH_FAILED: "That password is not right.",
  TOKEN_INVALID: "This link is not valid. Ask for a new one.",
  TOKEN_EXPIRED: "This link has expired. Ask for a new one.",
  TOKEN_REVOKED: "This link has been cancelled. Ask for a new one.",
  EMAIL_TAKEN: "That email already has an account.",
  INVITE_PENDING: "That address already has an invitation waiting.",
  SELF_CHANGE_FORBIDDEN: "You cannot make that change to your own account.",
  LAST_ADMIN_PROTECTED: "There must always be at least one active Admin.",
  ACCOUNT_NOT_POSTABLE: "That is a parent account. Choose one of its sub-accounts.",
  DUPLICATE_VALUE: "That value is already in use.",
  TAX_RULE_OVERLAP: "Another rule already covers those dates for the same supplier and category.",
  PERIOD_OVERLAP: "That period overlaps one that is already closed.",
  INVALID_TRANSITION: "This cannot be done from its current status.",
  SELF_APPROVAL_FORBIDDEN: "You cannot approve a document you created.",
  DOCUMENT_INCOMPLETE: "This is not complete yet. See what is missing below.",
  VOUCHER_UNBALANCED: "Debits and credits must be equal.",
  COMMENT_REQUIRED: "Add a comment explaining the decision.",
  REASON_REQUIRED: "Give a reason.",
  PERIOD_CLOSED: "That accounting period is closed.",
  REVERSAL_NOT_VOIDABLE: "A reversing voucher cannot be voided.",
  DOCUMENT_LOCKED: "This document has been submitted and can no longer be edited.",
  ALLOCATION_MISMATCH: "The split must add up exactly to the expense amount.",
  INACTIVE_REFERENCE: "One of the items chosen has been deactivated. Choose another.",
  TAX_RULE_MISSING: "No withholding rate is set for this supplier and category on that date.",
  PAYABLE_NEGATIVE: "The tax withheld is more than the amount owed.",
  UNSUPPORTED_FILE_TYPE: "Attach a JPEG, PNG or WebP image.",
  ATTACHMENT_LIMIT: "This document already has the most files it can hold.",
  IDEMPOTENCY_KEY_REQUIRED: "That action could not be made safe to repeat. Reload and try again.",
  IDEMPOTENCY_KEY_REUSED: "That action was already used for a different voucher. Reload and try again.",
  SOURCE_NOT_APPROVED: "Only an approved expense or purchase can become a voucher.",
  ALREADY_GENERATED: "A voucher has already been made from this.",
  POSTING_ACCOUNT_MISSING: "A posting account is not set. Set it under Posting accounts, then try again.",
  ACCOUNT_HAS_POSTINGS: "That account already has postings, so it cannot become a parent account.",
  INTERNAL_ERROR: "Something went wrong on our side. Try again; if it keeps happening, quote the reference below.",
  SERVICE_UNAVAILABLE: "The service is busy or unavailable. Try again in a moment.",
};

/** Codes where the server's own sentence says more than ours: it names the field, the role or the rule. */
const SERVER_WORDS_WIN: ReadonlySet<string> = new Set([
  "FORBIDDEN",
  "NOT_FOUND",
  "CONFLICT",
  "DUPLICATE_VALUE",
  "TAX_RULE_OVERLAP",
  "PERIOD_OVERLAP",
  "INVALID_TRANSITION",
  "DOCUMENT_INCOMPLETE",
  "VOUCHER_UNBALANCED",
  "ALLOCATION_MISMATCH",
  "INACTIVE_REFERENCE",
  "TAX_RULE_MISSING",
  "POSTING_ACCOUNT_MISSING",
  "ACCOUNT_HAS_POSTINGS",
  "ACCOUNT_NOT_POSTABLE",
  "PERIOD_CLOSED",
  "ALREADY_GENERATED",
  "BAD_REQUEST",
  "EMAIL_TAKEN",
  "INVITE_PENDING",
  "LAST_ADMIN_PROTECTED",
  "SELF_CHANGE_FORBIDDEN",
  "UNSUPPORTED_FILE_TYPE",
  "PAYLOAD_TOO_LARGE",
  "ATTACHMENT_LIMIT",
  "DOCUMENT_LOCKED",
  "PAYABLE_NEGATIVE",
]);

/** How long to wait, in words: "45 seconds", "3 minutes". */
export function waitText(seconds: number): string {
  if (seconds < 90) return `${Math.max(1, Math.ceil(seconds))} second${seconds <= 1 ? "" : "s"}`;
  const minutes = Math.ceil(seconds / 60);
  return `${minutes} minutes`;
}

/** The sentence to show a person for a failed call. */
export function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Try again.";
  if (error.code === "NETWORK") return "Daftar could not be reached. Check the connection and try again.";
  if (error.code === "RATE_LIMITED") {
    return error.retryAfter
      ? `Too many attempts. Wait ${waitText(error.retryAfter)}, then try again.`
      : DEFAULT_MESSAGES.RATE_LIMITED;
  }
  if (SERVER_WORDS_WIN.has(error.code) && error.detail) return error.detail;
  return DEFAULT_MESSAGES[error.code] ?? "Something went wrong. Try again.";
}
