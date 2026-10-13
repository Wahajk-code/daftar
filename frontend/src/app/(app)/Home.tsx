"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/api/client";
import { usePage } from "@/api/queries";
import type { Expense, ExpenseReport, Page, Purchase, PurchaseReport, Voucher, VoucherRegisterRow } from "@/api/types";
import { useMe, useZone } from "@/components/shell/MeContext";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { DateText, Money } from "@/components/ui/Format";
import { Panel, PageHeader } from "@/components/ui/Layout";
import { Stamp } from "@/components/ui/Stamp";
import { amountOf, href, titleOf, type Kind } from "@/lib/documents";
import { formatDate, startOfMonth, todayInZone } from "@/lib/dates";
import { ZERO_PAISA, fromPaisa, toPaisa } from "@/lib/money";
import styles from "./Home.module.css";

interface Item {
  key: string;
  kind: Kind;
  id: number;
  title: string;
  amount: string;
  by: string;
  date: string;
  status: Expense["status"];
}

function toItems(kind: Kind, rows: Array<Expense | Purchase | Voucher> | undefined): Item[] {
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

const KIND_NOUN: Record<Kind, string> = { expenses: "Expense", purchases: "Purchase", vouchers: "Voucher" };

function Queue({
  title,
  description,
  items,
  loading,
  error,
  empty,
  viewAll,
}: {
  title: string;
  description?: string;
  items: Item[] | undefined;
  loading: boolean;
  error: unknown;
  empty: string;
  viewAll?: { href: string; label: string };
}) {
  const columns: Column<Item>[] = [
    { key: "kind", header: "Type", cell: (item) => KIND_NOUN[item.kind], width: "96px" },
    {
      key: "title",
      header: "What",
      cell: (item) => (
        <Link href={href(item.kind, item.id)} className="user-text">
          {item.title}
        </Link>
      ),
    },
    { key: "by", header: "By", cell: (item) => item.by },
    { key: "date", header: "Dated", cell: (item) => <DateText value={item.date} />, width: "110px" },
    { key: "amount", header: "Amount", numeric: true, cell: (item) => <Money value={item.amount} />, width: "120px" },
    { key: "status", header: "Status", cell: (item) => <Stamp status={item.status} />, width: "120px" },
  ];
  return (
    <Panel
      title={
        <span>
          {title}
          {items ? <span className={styles.count}> {items.length}</span> : null}
        </span>
      }
      actions={viewAll ? <Link href={viewAll.href}>{viewAll.label}</Link> : undefined}
      flush
    >
      {description ? <p className={`${styles.note} muted`}>{description}</p> : null}
      <DataTable
        caption={title}
        columns={columns}
        rows={items?.slice(0, 8)}
        getKey={(item) => item.key}
        loading={loading}
        error={error}
        empty={{ title: empty }}
      />
    </Panel>
  );
}

function ApproverHome({ meId }: { meId: number }) {
  const expenses = usePage<Expense>("/expenses", { status: "submitted", limit: 100 });
  const purchases = usePage<Purchase>("/purchases", { status: "submitted", limit: 100 });
  const vouchers = usePage<Voucher>("/vouchers", { status: "submitted", limit: 100 });
  const mine = (rows: Array<Expense | Purchase | Voucher> | undefined) => rows?.filter((doc) => doc.created_by !== meId);
  const ready = expenses.data && purchases.data && vouchers.data;
  const items = ready
    ? [
        ...toItems("expenses", mine(expenses.data?.items)),
        ...toItems("purchases", mine(purchases.data?.items)),
        ...toItems("vouchers", mine(vouchers.data?.items)),
      ]
    : undefined;
  return (
    <Queue
      title="Waiting for your decision"
      description="Documents sent for approval by other people. Open one to read it and approve or reject."
      items={items}
      loading={!ready}
      error={expenses.error ?? purchases.error ?? vouchers.error}
      empty="Nothing is waiting for you."
      viewAll={{ href: "/approvals", label: "Open the approvals queue" }}
    />
  );
}

function BookkeeperHome({ meId }: { meId: number }) {
  const expenses = usePage<Expense>("/expenses", { status: "approved", limit: 100 });
  const purchases = usePage<Purchase>("/purchases", { status: "approved", limit: 100 });
  const toPost = usePage<Voucher>("/vouchers", { status: "approved", limit: 100 });
  const drafts = usePage<Voucher>("/vouchers", { status: "draft", limit: 100 });
  const rejectedVouchers = usePage<Voucher>("/vouchers", { status: "rejected", limit: 100 });
  const sources = expenses.data && purchases.data;
  const withoutVoucher = sources
    ? [
        ...toItems("expenses", expenses.data?.items.filter((doc) => !doc.voucher)),
        ...toItems("purchases", purchases.data?.items.filter((doc) => !doc.voucher)),
      ]
    : undefined;
  const mineBack = (rows: Voucher[] | undefined) => rows?.filter((doc) => doc.created_by === meId);
  const yours = drafts.data && rejectedVouchers.data ? toItems("vouchers", [...(mineBack(drafts.data.items) ?? []), ...(mineBack(rejectedVouchers.data.items) ?? [])]) : undefined;
  return (
    <>
      <Queue
        title="Approved, ready for a voucher"
        description="Approved expenses and purchases that do not have a payment voucher yet."
        items={withoutVoucher}
        loading={!sources}
        error={expenses.error ?? purchases.error}
        empty="Every approved item has its voucher."
      />
      <Queue
        title="Vouchers ready to post"
        items={toPost.data ? toItems("vouchers", toPost.data.items) : undefined}
        loading={toPost.isPending}
        error={toPost.error}
        empty="No voucher is waiting to be posted."
        viewAll={{ href: "/vouchers?status=approved", label: "See them all" }}
      />
      <Queue
        title="Your vouchers still to finish"
        description="Drafts you have not sent, and vouchers an approver sent back."
        items={yours}
        loading={!yours && !(drafts.error || rejectedVouchers.error)}
        error={drafts.error ?? rejectedVouchers.error}
        empty="You have no unfinished vouchers."
      />
    </>
  );
}

function StaffHome() {
  const drafts = usePage<Expense>("/expenses", { mine: true, status: "draft", limit: 100 });
  const rejected = usePage<Expense>("/expenses", { mine: true, status: "rejected", limit: 100 });
  const submitted = usePage<Expense>("/expenses", { mine: true, status: "submitted", limit: 100 });
  return (
    <>
      <Queue
        title="Sent back to you"
        description="A reviewer rejected these. Open one to read the comment, change it and send it again."
        items={rejected.data ? toItems("expenses", rejected.data.items) : undefined}
        loading={rejected.isPending}
        error={rejected.error}
        empty="Nothing has been sent back."
      />
      <Queue
        title="Your drafts"
        description="Not sent yet. Add the receipt and send them when they are ready."
        items={drafts.data ? toItems("expenses", drafts.data.items) : undefined}
        loading={drafts.isPending}
        error={drafts.error}
        empty="You have no drafts."
        viewAll={{ href: "/expenses/new", label: "New expense" }}
      />
      <Queue
        title="Waiting for approval"
        items={submitted.data ? toItems("expenses", submitted.data.items) : undefined}
        loading={submitted.isPending}
        error={submitted.error}
        empty="Nothing of yours is waiting."
        viewAll={{ href: "/expenses?mine=true", label: "All your expenses" }}
      />
    </>
  );
}

/** Real figures for the month so far, from the same reports the Reports screen shows. */
function MonthFigures() {
  const zone = useZone();
  const today = todayInZone(zone);
  const from = startOfMonth(today);
  const range = { date_from: from, date_to: today };
  const expenses = useQuery({ queryKey: ["report", "expenses", range], queryFn: () => api<ExpenseReport>("/reports/expenses", { query: range }) });
  const purchases = useQuery({ queryKey: ["report", "purchases", range], queryFn: () => api<PurchaseReport>("/reports/purchases", { query: range }) });
  const posted = useQuery({
    queryKey: ["report", "register", range],
    queryFn: () => api<Page<VoucherRegisterRow>>("/reports/vouchers", { query: { ...range, statuses: ["posted"], limit: 1 } }),
  });

  const figures = [
    { label: "Expenses", count: expenses.data?.totals.expenses, amount: expenses.data?.totals.amount, to: "/reports?report=expenses" },
    { label: "Purchases", count: purchases.data?.totals.purchases, amount: purchases.data?.totals.gross, to: "/reports?report=purchases" },
    { label: "Vouchers posted", count: posted.data?.total, amount: undefined, to: "/vouchers?status=posted" },
  ];

  const byCentre = new Map<string, bigint>();
  for (const row of expenses.data?.rows ?? []) {
    const name = row.cost_center_name ? row.cost_center_name : "No cost centre";
    byCentre.set(name, (byCentre.get(name) ?? ZERO_PAISA) + (toPaisa(row.amount) ?? ZERO_PAISA));
  }
  const ranked = [...byCentre.entries()].sort((a, b) => (b[1] > a[1] ? 1 : b[1] < a[1] ? -1 : 0));
  const largest = ranked[0]?.[1] ?? ZERO_PAISA;

  return (
    <>
      <Panel title="This month so far" id="month">
        <ul className={styles.figures}>
          {figures.map((figure) => (
            <li key={figure.label}>
              <Link href={figure.to} className={styles.figure}>
                <span className={styles.figureLabel}>{figure.label}</span>
                <span className={styles.figureCount}>{figure.count ?? "..."}</span>
                {figure.amount !== undefined ? <Money value={figure.amount} className={styles.figureAmount} /> : <span />}
              </Link>
            </li>
          ))}
        </ul>
        <p className={`${styles.note} faint`}>Approved and posted documents dated this month.</p>
      </Panel>
      <Panel title="Spend by cost centre" id="centres">
        {expenses.isPending ? (
          <p className="muted">Loading</p>
        ) : ranked.length === 0 ? (
          <p className="muted">Nothing has been approved this month yet.</p>
        ) : (
          <ul className={styles.bars}>
            {ranked.map(([name, paisa]) => (
              <li key={name}>
                <span className={styles.barLabel}>{name}</span>
                <span className={styles.barTrack} aria-hidden>
                  <span className={styles.barFill} style={{ width: `${largest > ZERO_PAISA ? Number((paisa * BigInt(100)) / largest) : 0}%` }} />
                </span>
                <Money value={fromPaisa(paisa)} />
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  );
}

export function Home() {
  const me = useMe();
  const zone = useZone();
  const isOffice = me.role !== "staff";
  return (
    <>
      <PageHeader title="Home" description={`Today is ${formatDate(todayInZone(zone))}.`} />
      <div className={isOffice ? styles.grid : styles.single}>
        <div className={styles.queues}>
          {me.role === "staff" ? <StaffHome /> : null}
          {me.role === "approver" ? <ApproverHome meId={me.id} /> : null}
          {me.role === "accountant" ? <BookkeeperHome meId={me.id} /> : null}
          {me.role === "admin" ? (
            <>
              <ApproverHome meId={me.id} />
              <BookkeeperHome meId={me.id} />
            </>
          ) : null}
        </div>
        {isOffice ? (
          <div className={styles.side}>
            <MonthFigures />
          </div>
        ) : null}
      </div>
    </>
  );
}
