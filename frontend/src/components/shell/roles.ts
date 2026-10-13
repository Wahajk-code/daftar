import type { Role } from "@/api/types";

export const ROLE_NAME: Record<Role, string> = { admin: "Admin", accountant: "Accountant", approver: "Approver", staff: "Staff" };

/** What a role does here, in a sentence. Used by the tour and the Help center. */
export const ROLE_LINE: Record<Role, string> = {
  admin: "You look after the people and see everything the other roles see.",
  accountant: "You turn approved expenses and purchases into vouchers, post them, and keep the books in order.",
  approver: "You read what others send for approval and decide: approve it, or send it back with a reason.",
  staff: "You record your expenses with their receipts, send them for approval, and follow where each one stands.",
};

/** The jobs of a role, in the order they usually happen. */
export const ROLE_TASKS: Record<Role, string[]> = {
  admin: [
    "Invite people by email and choose their role. You never see or set a password.",
    "Approve what is waiting if the approvers are away.",
    "Close an accounting period when its books are final.",
    "Read the audit log to see who changed what.",
  ],
  accountant: [
    "Open an approved expense or purchase and generate its payment voucher.",
    "Check the voucher lines, send it for approval, and post it when approved.",
    "Void a posted voucher with a reason; a reversing voucher is posted for you.",
    "Keep vendors, accounts, tax rates and posting accounts up to date.",
  ],
  approver: [
    "Open what is waiting for your decision and read it with its receipt.",
    "Approve it, or reject it with a comment the author will see.",
    "You can never approve something you wrote yourself.",
    "Use Reports to see where the money went.",
  ],
  staff: [
    "Press New and write an expense: what it was for, the amount, and the category.",
    "Attach the receipt, save it as a draft, and send it for approval.",
    "If it comes back, read the reason in its history, fix it and send it again.",
    "Follow each expense until it is posted.",
  ],
};

/** The four roles with what each may do: for choosing a role when inviting or changing someone. */
export const ROLE_OPTIONS: Array<{ value: Role; label: string; about: string }> = [
  { value: "admin", label: "Admin", about: "Manages people and roles, closes periods, reads the audit log, and can do everything else." },
  { value: "accountant", label: "Accountant", about: "Keeps the books: master data, tax rates, purchases, vouchers, posting and voiding." },
  { value: "approver", label: "Approver", about: "Reads everything and approves or rejects documents other people wrote." },
  { value: "staff", label: "Staff", about: "Writes and sends their own expenses with receipts." },
];
