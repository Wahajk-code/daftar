/** What the screens share about the three kinds of document. */
import type { DocumentStatus, Expense, Purchase, Voucher } from "@/api/types";

export type Kind = "expenses" | "purchases" | "vouchers";

export const KIND_LABEL: Record<Kind, { singular: string; plural: string }> = {
  expenses: { singular: "Expense", plural: "Expenses" },
  purchases: { singular: "Purchase", plural: "Purchases" },
  vouchers: { singular: "Voucher", plural: "Vouchers" },
};

export const STATUS_OPTIONS: Array<{ value: DocumentStatus; label: string }> = [
  { value: "draft", label: "Draft" },
  { value: "submitted", label: "Submitted" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "posted", label: "Posted" },
  { value: "void", label: "Void" },
];

export const PAYMENT_METHODS = [
  { value: "cash", label: "Cash" },
  { value: "bank_transfer", label: "Bank transfer" },
  { value: "card", label: "Card" },
  { value: "cheque", label: "Cheque" },
] as const;

export function paymentLabel(value: string): string {
  return PAYMENT_METHODS.find((method) => method.value === value)?.label ?? value;
}

export function href(kind: Kind, id: number): string {
  return `/${kind}/${id}`;
}

/** A line that says what a document is, for a list or a queue. */
export function titleOf(kind: Kind, doc: Expense | Purchase | Voucher): string {
  if (kind === "expenses") {
    const expense = doc as Expense;
    return expense.description || expense.category_name;
  }
  if (kind === "purchases") {
    const purchase = doc as Purchase;
    return purchase.description || purchase.vendor_name;
  }
  const voucher = doc as Voucher;
  return voucher.description || voucher.number || `Voucher ${voucher.id}`;
}

export function amountOf(kind: Kind, doc: Expense | Purchase | Voucher): string {
  if (kind === "expenses") return (doc as Expense).amount;
  if (kind === "purchases") return (doc as Purchase).gross_total;
  return (doc as Voucher).total_debit;
}

export const VOUCHER_TYPES = [
  { value: "PV", label: "Payment voucher" },
  { value: "RV", label: "Receipt voucher" },
  { value: "JV", label: "Journal voucher" },
] as const;

export function voucherTypeLabel(value: string): string {
  return VOUCHER_TYPES.find((type) => type.value === value)?.label ?? value;
}
