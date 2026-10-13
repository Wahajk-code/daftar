"use client";

import { usePage } from "@/api/queries";
import type { Expense, Purchase, Voucher } from "@/api/types";
import { useMe } from "@/components/shell/MeContext";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { DateText, Money, TwoLine } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { Stamp, Tag } from "@/components/ui/Stamp";
import { KIND_LABEL, amountOf, href, titleOf, type Kind } from "@/lib/documents";
import { useUrlState } from "@/lib/url-state";
import styles from "./Approvals.module.css";

interface Row {
  key: string;
  kind: Kind;
  id: number;
  title: string;
  by: string;
  date: string;
  amount: string;
  status: Expense["status"];
}

function rows(kind: Kind, docs: Array<Expense | Purchase | Voucher> | undefined, meId: number): Row[] {
  return (docs ?? [])
    .filter((doc) => doc.created_by !== meId)
    .map((doc) => ({ key: `${kind}-${doc.id}`, kind, id: doc.id, title: titleOf(kind, doc), by: doc.created_by_name, date: doc.document_date, amount: amountOf(kind, doc), status: doc.status }));
}

const KIND_TONE = { expenses: "teal", purchases: "info", vouchers: "violet" } as const;

const TABS: Array<{ value: "all" | Kind; label: string }> = [
  { value: "all", label: "Everything" },
  { value: "expenses", label: "Expenses" },
  { value: "purchases", label: "Purchases" },
  { value: "vouchers", label: "Vouchers" },
];

/** Everything sent for approval by someone else, oldest first, in one place. */
export function Approvals() {
  const me = useMe();
  const url = useUrlState();
  const tab = (url.get("kind") || "all") as "all" | Kind;
  const expenses = usePage<Expense>("/expenses", { status: "submitted", limit: 100, sort: "document_date" });
  const purchases = usePage<Purchase>("/purchases", { status: "submitted", limit: 100, sort: "document_date" });
  const vouchers = usePage<Voucher>("/vouchers", { status: "submitted", limit: 100, sort: "document_date" });

  const ready = expenses.data && purchases.data && vouchers.data;
  const all: Row[] | undefined = ready
    ? [...rows("expenses", expenses.data?.items, me.id), ...rows("purchases", purchases.data?.items, me.id), ...rows("vouchers", vouchers.data?.items, me.id)].sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id)
    : undefined;
  const shown = all?.filter((row) => tab === "all" || row.kind === tab);
  const count = (kind: "all" | Kind) => (all ?? []).filter((row) => kind === "all" || row.kind === kind).length;

  const columns: Column<Row>[] = [
    { key: "title", header: "What", primary: true, cell: (row) => <TwoLine title={row.title} sub={`Sent by ${row.by}`} />, title: (row) => row.title, maxWidth: "40ch" },
    { key: "kind", header: "Type", cell: (row) => <Tag tone={KIND_TONE[row.kind]}>{KIND_LABEL[row.kind].singular}</Tag>, width: "120px" },
    { key: "date", header: "Dated", cell: (row) => <DateText value={row.date} />, width: "120px" },
    { key: "amount", header: "Amount", numeric: true, cell: (row) => <Money value={row.amount} />, width: "140px" },
    { key: "status", header: "Status", cell: (row) => <Stamp status={row.status} />, width: "130px" },
  ];

  return (
    <>
      <PageHeader title="Approvals" description="Documents sent for approval by other people. Nobody approves their own." />
      <Panel flush>
        <div className={styles.tabs} data-noprint role="tablist" aria-label="Kind of document">
          {TABS.map((item) => (
            <button key={item.value} type="button" role="tab" aria-selected={tab === item.value} onClick={() => url.set({ kind: item.value === "all" ? null : item.value })}>
              {item.label}
              {all ? <span className={styles.count}>{count(item.value)}</span> : null}
            </button>
          ))}
        </div>
        <DataTable
          caption="Documents waiting for a decision"
          columns={columns}
          rows={shown}
          getKey={(row) => row.key}
          rowHref={(row) => href(row.kind, row.id)}
          loading={!ready}
          error={expenses.error ?? purchases.error ?? vouchers.error}
          empty={{ title: "Nothing is waiting for you", hint: "When someone sends a document for approval, it appears here." }}
        />
      </Panel>
    </>
  );
}
