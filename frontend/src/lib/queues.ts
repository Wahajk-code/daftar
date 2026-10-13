"use client";

import { usePage } from "@/api/queries";
import type { Expense, Me, Purchase, Voucher } from "@/api/types";
import { amountOf, titleOf, type Kind } from "@/lib/documents";

/** One document as a line in a queue. */
export interface QueueItem {
  key: string;
  kind: Kind;
  id: number;
  title: string;
  amount: string;
  by: string;
  date: string;
  status: Expense["status"];
}

/** A list of documents that wait for something from this person (or that they should keep an eye on). */
export interface WorkQueue {
  key: string;
  title: string;
  description?: string;
  /** Needs this person to act: counted on the bell. Other queues are for information. */
  attention: boolean;
  items: QueueItem[] | undefined;
  loading: boolean;
  error: unknown;
  empty: string;
  viewAll?: { href: string; label: string };
}

function toItems(kind: Kind, rows: Array<Expense | Purchase | Voucher> | undefined): QueueItem[] {
  return (rows ?? []).map((doc) => ({
    key: `${kind}-${doc.id}`,
    kind,
    id: doc.id,
    title: titleOf(kind, doc),
    amount: amountOf(kind, doc),
    by: doc.created_by_name,
    date: doc.document_date,
    status: doc.status,
  }));
}

function useApproverQueues(meId: number, enabled: boolean): WorkQueue[] {
  const expenses = usePage<Expense>("/expenses", { status: "submitted", limit: 100 }, { enabled });
  const purchases = usePage<Purchase>("/purchases", { status: "submitted", limit: 100 }, { enabled });
  const vouchers = usePage<Voucher>("/vouchers", { status: "submitted", limit: 100 }, { enabled });
  const others = (rows: Array<Expense | Purchase | Voucher> | undefined) => rows?.filter((doc) => doc.created_by !== meId);
  const ready = expenses.data && purchases.data && vouchers.data;
  return [
    {
      key: "decide",
      title: "Waiting for your decision",
      description: "Documents sent for approval by other people. Open one to read it and approve or reject.",
      attention: true,
      items: ready
        ? [
            ...toItems("expenses", others(expenses.data?.items)),
            ...toItems("purchases", others(purchases.data?.items)),
            ...toItems("vouchers", others(vouchers.data?.items)),
          ]
        : undefined,
      loading: !ready,
      error: expenses.error ?? purchases.error ?? vouchers.error,
      empty: "Nothing is waiting for you.",
      viewAll: { href: "/approvals", label: "Open the approvals queue" },
    },
  ];
}

function useBookkeeperQueues(meId: number, enabled: boolean): WorkQueue[] {
  const expenses = usePage<Expense>("/expenses", { status: "approved", limit: 100 }, { enabled });
  const purchases = usePage<Purchase>("/purchases", { status: "approved", limit: 100 }, { enabled });
  const toPost = usePage<Voucher>("/vouchers", { status: "approved", limit: 100 }, { enabled });
  const drafts = usePage<Voucher>("/vouchers", { status: "draft", limit: 100 }, { enabled });
  const rejected = usePage<Voucher>("/vouchers", { status: "rejected", limit: 100 }, { enabled });
  const sources = expenses.data && purchases.data;
  const yours =
    drafts.data && rejected.data
      ? toItems("vouchers", [...drafts.data.items, ...rejected.data.items].filter((doc) => doc.created_by === meId))
      : undefined;
  return [
    {
      key: "needs-voucher",
      title: "Approved, ready for a voucher",
      description: "Approved expenses and purchases that do not have a payment voucher yet.",
      attention: true,
      items: sources
        ? [
            ...toItems("expenses", expenses.data?.items.filter((doc) => !doc.voucher)),
            ...toItems("purchases", purchases.data?.items.filter((doc) => !doc.voucher)),
          ]
        : undefined,
      loading: !sources,
      error: expenses.error ?? purchases.error,
      empty: "Every approved item has its voucher.",
    },
    {
      key: "to-post",
      title: "Vouchers ready to post",
      attention: true,
      items: toPost.data ? toItems("vouchers", toPost.data.items) : undefined,
      loading: toPost.isPending,
      error: toPost.error,
      empty: "No voucher is waiting to be posted.",
      viewAll: { href: "/vouchers?status=approved", label: "See them all" },
    },
    {
      key: "unfinished",
      title: "Your vouchers still to finish",
      description: "Drafts you have not sent, and vouchers an approver sent back.",
      attention: false,
      items: yours,
      loading: !yours && !(drafts.error || rejected.error),
      error: drafts.error ?? rejected.error,
      empty: "You have no unfinished vouchers.",
    },
  ];
}

function useStaffQueues(enabled: boolean): WorkQueue[] {
  const drafts = usePage<Expense>("/expenses", { mine: true, status: "draft", limit: 100 }, { enabled });
  const rejected = usePage<Expense>("/expenses", { mine: true, status: "rejected", limit: 100 }, { enabled });
  const submitted = usePage<Expense>("/expenses", { mine: true, status: "submitted", limit: 100 }, { enabled });
  return [
    {
      key: "sent-back",
      title: "Sent back to you",
      description: "A reviewer rejected these. Open one to read the comment, change it and send it again.",
      attention: true,
      items: rejected.data ? toItems("expenses", rejected.data.items) : undefined,
      loading: rejected.isPending,
      error: rejected.error,
      empty: "Nothing has been sent back.",
    },
    {
      key: "drafts",
      title: "Your drafts",
      description: "Not sent yet. Add the receipt and send them when they are ready.",
      attention: false,
      items: drafts.data ? toItems("expenses", drafts.data.items) : undefined,
      loading: drafts.isPending,
      error: drafts.error,
      empty: "You have no drafts.",
    },
    {
      key: "waiting",
      title: "Waiting for approval",
      attention: false,
      items: submitted.data ? toItems("expenses", submitted.data.items) : undefined,
      loading: submitted.isPending,
      error: submitted.error,
      empty: "Nothing of yours is waiting.",
      viewAll: { href: "/expenses?mine=true", label: "All your expenses" },
    },
  ];
}

/**
 * The lists a person works from, chosen by role. The home screen draws them as cards and the bell in the header counts the
 * ones that need action. Every hook runs on every render so their order never changes; the ones a role does not use are
 * switched off and fetch nothing.
 */
export function useWorkQueues(me: Pick<Me, "id" | "role">): WorkQueue[] {
  const approver = useApproverQueues(me.id, me.role === "approver" || me.role === "admin");
  const bookkeeper = useBookkeeperQueues(me.id, me.role === "accountant" || me.role === "admin");
  const staff = useStaffQueues(me.role === "staff");
  if (me.role === "staff") return staff;
  if (me.role === "approver") return approver;
  if (me.role === "accountant") return bookkeeper;
  return [...approver, ...bookkeeper];
}
