/** Names for the schemas the screens use, taken from the generated file. Nothing here is written by hand twice. */
import type { components } from "./schema";

type S = components["schemas"];

export type ErrorCode = S["ErrorCode"];
export type FieldProblem = S["ProblemFieldError"];
export type Problem = S["ProblemDetail"];
export type Me = S["MeRead"];
export type Role = S["Role"];
export type DocumentStatus = S["DocumentStatus"];

export type Expense = S["ExpenseRead"];
export type ExpenseCreate = S["ExpenseCreate"];
export type ExpenseUpdate = S["ExpenseUpdate"];
export type Allocation = S["AllocationRead"];
export type AllocationPreview = S["AllocationPreviewRead"];
export type Attachment = S["AttachmentRead"];
export type HistoryItem = S["HistoryItem"];
export type DuplicateWarning = S["DuplicateWarningRead"];

export type Purchase = S["PurchaseRead"];
export type PurchaseCreate = S["PurchaseCreate"];
export type PurchaseUpdate = S["PurchaseUpdate"];
export type PurchaseLine = S["PurchaseLineRead"];
export type PurchasePreview = S["PurchasePreviewRead"];

export type Voucher = S["VoucherRead"];
export type VoucherCreate = S["VoucherCreate"];
export type VoucherLine = S["VoucherLineRead"];
export type VoucherRef = S["VoucherRef"];
export type BalanceCheck = S["BalanceCheckRead"];
export type VoidResult = S["VoidResult"];

export type Vendor = S["VendorRead"];
export type Account = S["AccountRead"];
export type Category = S["CategoryRead"];
export type CostCenter = S["CostCenterRead"];
export type Project = S["ProjectRead"];
export type TaxRule = S["TaxRuleRead"];
export type Period = S["PeriodRead"];
export type PostingAccount = S["PostingAccountRead"];
export type AccountingSettings = S["AccountingSettingsRead"];

export type User = S["UserRead"];
export type Invite = S["InviteRead"];

export type ExpenseReport = S["ExpenseReport"];
export type PurchaseReport = S["PurchaseReport"];
export type VoucherRegisterRow = S["VoucherRegisterRow"];
export type ActivityReport = S["ActivityReport"];

/** The paged answer every list gives. */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
