"use client";

import { IconDownload } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, download } from "@/api/client";
import { messageFor } from "@/api/errors";
import { useAction } from "@/api/queries";
import type { ActivityReport, DocumentStatus, ExpenseReport, Page, PurchaseReport, VoucherRegisterRow } from "@/api/types";
import { useZone } from "@/components/shell/MeContext";
import { Button } from "@/components/ui/Button";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { CheckboxField, SelectField, TextField } from "@/components/ui/Field";
import { DateText, Identifier, Money } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { Banner } from "@/components/ui/States";
import { Stamp, Tag } from "@/components/ui/Stamp";
import { STATUS_OPTIONS, VOUCHER_TYPES } from "@/lib/documents";
import { startOfMonth, todayInZone } from "@/lib/dates";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";
import styles from "./Reports.module.css";

type ReportName = "expenses" | "purchases" | "vouchers" | "activity";

const REPORTS: Array<{ value: ReportName; label: string; about: string }> = [
  { value: "expenses", label: "Expenses", about: "By type and cost centre. An indirect expense appears under every cost centre it was shared across." },
  { value: "purchases", label: "Purchases", about: "By vendor, with registered and unregistered vendors kept apart." },
  { value: "vouchers", label: "Voucher register", about: "Every numbered voucher in order, with a void one beside its reversal." },
  { value: "activity", label: "Activity by person", about: "What each person created, sent, had sent back, decided, posted and voided." },
];

const SPEND_STATUSES: DocumentStatus[] = ["draft", "submitted", "approved", "rejected", "posted"];

function StatusChoice({ chosen, options, onChange }: { chosen: string[]; options: Array<{ value: string; label: string }>; onChange: (next: string[]) => void }) {
  return (
    <fieldset className={styles.statuses}>
      <legend>Include</legend>
      {options.map((option) => (
        <CheckboxField
          key={option.value}
          label={option.label}
          checked={chosen.includes(option.value)}
          onChange={(event) => onChange(event.target.checked ? [...chosen, option.value] : chosen.filter((value) => value !== option.value))}
        />
      ))}
    </fieldset>
  );
}

export function Reports() {
  const zone = useZone();
  const url = useUrlState();
  const name = (url.get("report") || "expenses") as ReportName;
  const today = todayInZone(zone);
  const from = url.get("date_from") || startOfMonth(today);
  const to = url.get("date_to") || today;
  const defaultStatuses = name === "vouchers" ? ["posted", "void"] : ["approved", "posted"];
  const statuses = url.params.getAll("statuses").length > 0 ? url.params.getAll("statuses") : defaultStatuses;
  const range = { date_from: from, date_to: to };
  const current = REPORTS.find((report) => report.value === name) ?? REPORTS[0];

  const exportCsv = useAction<void, void>({
    mutationFn: () =>
      download(`/reports/${name}/csv`, {
        ...range,
        ...(name !== "activity" ? { statuses } : {}),
        ...(name === "vouchers" ? { voucher_type: url.get("voucher_type") } : {}),
        ...(name === "purchases" ? { registered: url.get("registered") } : {}),
      }),
    success: "Download started",
    invalidate: [],
  });

  const setStatuses = (next: string[]) => url.setList("statuses", next);

  return (
    <>
      <PageHeader title="Reports" description={current.about} actions={<Button icon={<IconDownload size={18} stroke={1.75} aria-hidden />} pending={exportCsv.isPending} onClick={() => exportCsv.mutate()}>Download CSV</Button>} />
      <Panel flush>
        <div className={styles.tabs} data-noprint role="tablist" aria-label="Report">
          {REPORTS.map((report) => (
            <button key={report.value} type="button" role="tab" aria-selected={name === report.value} onClick={() => url.set({ report: report.value === "expenses" ? null : report.value, statuses: null, offset: null, voucher_type: null, registered: null })}>
              {report.label}
            </button>
          ))}
        </div>
        <p className="print-only">
          {current.label}, {from} to {to}.
        </p>
        <div className={styles.filters} data-noprint>
          <TextField label="From" type="date" value={from} onChange={(event) => url.set({ date_from: event.target.value })} />
          <TextField label="To" type="date" value={to} onChange={(event) => url.set({ date_to: event.target.value })} />
          {name === "expenses" || name === "purchases" ? <StatusChoice chosen={statuses} options={SPEND_STATUSES.map((value) => ({ value, label: STATUS_OPTIONS.find((option) => option.value === value)?.label ?? value }))} onChange={setStatuses} /> : null}
          {name === "vouchers" ? <StatusChoice chosen={statuses} options={STATUS_OPTIONS.filter((option) => ["draft", "submitted", "approved", "posted", "void"].includes(option.value))} onChange={setStatuses} /> : null}
          {name === "vouchers" ? <SelectField label="Type" value={url.get("voucher_type")} onChange={(event) => url.set({ voucher_type: event.target.value })} options={VOUCHER_TYPES.map((type) => ({ value: type.value, label: type.label }))} placeholder="All types" /> : null}
          {name === "purchases" ? <SelectField label="Vendors" value={url.get("registered")} onChange={(event) => url.set({ registered: event.target.value })} options={[{ value: "true", label: "Registered" }, { value: "false", label: "Not registered" }]} placeholder="All vendors" /> : null}
        </div>
        {name === "expenses" ? <ExpensesReport range={range} statuses={statuses} /> : null}
        {name === "purchases" ? <PurchasesReport range={range} statuses={statuses} registered={url.get("registered")} /> : null}
        {name === "vouchers" ? <RegisterReport range={range} statuses={statuses} type={url.get("voucher_type")} /> : null}
        {name === "activity" ? <ActivityTable range={range} /> : null}
      </Panel>
      {exportCsv.error ? <Banner tone="negative" title="The download failed">{messageFor(exportCsv.error)}</Banner> : null}
    </>
  );
}

type Range = { date_from: string; date_to: string };

function ExpensesReport({ range, statuses }: { range: Range; statuses: string[] }) {
  const report = useQuery({ queryKey: ["report", "expenses", range, statuses], queryFn: () => api<ExpenseReport>("/reports/expenses", { query: { ...range, statuses } }) });
  const columns: Column<ExpenseReport["rows"][number]>[] = [
    { key: "type", header: "Type", cell: (row) => <Tag tone={row.expense_type === "direct" ? "teal" : "violet"}>{row.expense_type === "direct" ? "Direct" : "Indirect"}</Tag>, width: "120px" },
    { key: "centre", header: "Cost centre", cell: (row) => (row.cost_center_name ? `${row.cost_center_code} ${row.cost_center_name}` : <span className="faint">No cost centre (project or product)</span>) },
    { key: "count", header: "Expenses", numeric: true, cell: (row) => row.expenses, width: "110px" },
    { key: "amount", header: "Amount", numeric: true, cell: (row) => <Money value={row.amount} />, width: "150px" },
  ];
  return (
    <DataTable
      caption="Expenses by type and cost centre"
      columns={columns}
      rows={report.data?.rows}
      getKey={(row) => `${row.expense_type}-${row.cost_center_code}`}
      loading={report.isPending}
      error={report.error}
      onRetry={() => report.refetch()}
      empty={{ title: "No expenses in this period", hint: "Change the dates or the statuses included." }}
      footer={
        report.data ? (
          <tr>
            <th scope="row" colSpan={2}>All expenses, each counted once</th>
            <td className="num">{report.data.totals.expenses}</td>
            <td className="num"><Money value={report.data.totals.amount} strong /></td>
          </tr>
        ) : undefined
      }
    />
  );
}

function PurchasesReport({ range, statuses, registered }: { range: Range; statuses: string[]; registered: string }) {
  const report = useQuery({ queryKey: ["report", "purchases", range, statuses, registered], queryFn: () => api<PurchaseReport>("/reports/purchases", { query: { ...range, statuses, registered } }) });
  const columns: Column<PurchaseReport["rows"][number]>[] = [
    { key: "vendor", header: "Vendor", cell: (row) => <span className="user-text">{row.vendor_name}</span> },
    { key: "reg", header: "Registration", cell: (row) => <Tag tone={row.registered ? "positive" : "caution"}>{row.registered ? "Registered" : "Not registered"}</Tag>, width: "150px" },
    { key: "count", header: "Purchases", numeric: true, cell: (row) => row.purchases, width: "100px" },
    { key: "sub", header: "Subtotal", numeric: true, cell: (row) => <Money value={row.subtotal} />, width: "130px" },
    { key: "tax", header: "Sales tax", numeric: true, cell: (row) => <Money value={row.sales_tax} />, width: "120px" },
    { key: "gross", header: "Gross", numeric: true, cell: (row) => <Money value={row.gross} />, width: "130px" },
    { key: "wh", header: "Sales tax withheld", numeric: true, cell: (row) => <Money value={row.sales_tax_withheld} />, width: "150px" },
    { key: "inc", header: "Income tax withheld", numeric: true, cell: (row) => <Money value={row.income_tax_withheld} />, width: "160px" },
    { key: "pay", header: "Payable", numeric: true, cell: (row) => <Money value={row.payable} />, width: "130px" },
  ];
  const totals = report.data;
  return (
    <DataTable
      caption="Purchases by vendor"
      columns={columns}
      rows={report.data?.rows}
      getKey={(row) => `${row.vendor_id}-${row.registered}`}
      loading={report.isPending}
      error={report.error}
      onRetry={() => report.refetch()}
      empty={{ title: "No purchases in this period", hint: "Change the dates or the statuses included." }}
      footer={
        totals ? (
          <>
            <tr>
              <th scope="row" colSpan={2}>Registered vendors</th>
              <td className="num">{totals.registered.purchases}</td>
              <td className="num"><Money value={totals.registered.subtotal} /></td>
              <td className="num"><Money value={totals.registered.sales_tax} /></td>
              <td className="num"><Money value={totals.registered.gross} /></td>
              <td className="num"><Money value={totals.registered.sales_tax_withheld} /></td>
              <td className="num"><Money value={totals.registered.income_tax_withheld} /></td>
              <td className="num"><Money value={totals.registered.payable} /></td>
            </tr>
            <tr>
              <th scope="row" colSpan={2}>Not registered</th>
              <td className="num">{totals.unregistered.purchases}</td>
              <td className="num"><Money value={totals.unregistered.subtotal} /></td>
              <td className="num"><Money value={totals.unregistered.sales_tax} /></td>
              <td className="num"><Money value={totals.unregistered.gross} /></td>
              <td className="num"><Money value={totals.unregistered.sales_tax_withheld} /></td>
              <td className="num"><Money value={totals.unregistered.income_tax_withheld} /></td>
              <td className="num"><Money value={totals.unregistered.payable} /></td>
            </tr>
            <tr>
              <th scope="row" colSpan={2}>All purchases</th>
              <td className="num">{totals.totals.purchases}</td>
              <td className="num"><Money value={totals.totals.subtotal} strong /></td>
              <td className="num"><Money value={totals.totals.sales_tax} strong /></td>
              <td className="num"><Money value={totals.totals.gross} strong /></td>
              <td className="num"><Money value={totals.totals.sales_tax_withheld} strong /></td>
              <td className="num"><Money value={totals.totals.income_tax_withheld} strong /></td>
              <td className="num"><Money value={totals.totals.payable} strong /></td>
            </tr>
          </>
        ) : undefined
      }
    />
  );
}

function RegisterReport({ range, statuses, type }: { range: Range; statuses: string[]; type: string }) {
  const url = useUrlState();
  const offset = Number(url.get("offset") || 0);
  const report = useQuery({
    queryKey: ["report", "register", range, statuses, type, offset],
    queryFn: () => api<Page<VoucherRegisterRow>>("/reports/vouchers", { query: { ...range, statuses, voucher_type: type, limit: PAGE_SIZE, offset } }),
    placeholderData: (previous) => previous,
  });
  const columns: Column<VoucherRegisterRow>[] = [
    { key: "number", header: "Number", cell: (row) => <Identifier value={row.number} voided={row.status === "void"} />, width: "170px" },
    { key: "date", header: "Dated", cell: (row) => <DateText value={row.document_date} />, width: "120px" },
    { key: "narration", header: "Narration", cell: (row) => <span className="user-text">{row.description}</span> },
    {
      key: "from",
      header: "From",
      cell: (row) =>
        row.reversal_of_number ? (
          <span>Reverses <Identifier value={row.reversal_of_number} /></span>
        ) : row.expense_id ? (
          <Link href={`/expenses/${row.expense_id}`}>Expense {row.expense_id}</Link>
        ) : row.purchase_id ? (
          <Link href={`/purchases/${row.purchase_id}`}>Purchase {row.purchase_id}</Link>
        ) : (
          <span className="faint">By hand</span>
        ),
      width: "190px",
    },
    { key: "total", header: "Total", numeric: true, cell: (row) => <Money value={row.total} />, width: "140px" },
    { key: "status", header: "Status", cell: (row) => <Stamp status={row.status} />, width: "120px" },
  ];
  return (
    <>
      <DataTable
        caption="Voucher register"
        columns={columns}
        rows={report.data?.items}
        getKey={(row) => `${row.number}-${row.document_date}-${row.total}-${row.reversal_of_number}`}
        loading={report.isPending}
        error={report.error}
        onRetry={() => report.refetch()}
        empty={{ title: "No vouchers in this period", hint: "Change the dates or the statuses included." }}
      />
      {report.data ? <Pagination total={report.data.total} limit={PAGE_SIZE} offset={offset} onOffset={(next) => url.set({ offset: next })} noun="vouchers" /> : null}
    </>
  );
}

function ActivityTable({ range }: { range: Range }) {
  const report = useQuery({ queryKey: ["report", "activity", range], queryFn: () => api<ActivityReport>("/reports/activity", { query: range }) });
  const columns: Column<ActivityReport["rows"][number]>[] = [
    { key: "person", header: "Person", cell: (row) => <span className="user-text">{row.full_name}</span> },
    { key: "role", header: "Role", cell: (row) => row.role, width: "110px" },
    { key: "e", header: "Expenses made", numeric: true, cell: (row) => row.expenses_created },
    { key: "p", header: "Purchases made", numeric: true, cell: (row) => row.purchases_created },
    { key: "v", header: "Vouchers made", numeric: true, cell: (row) => row.vouchers_created },
    { key: "s", header: "Sent for approval", numeric: true, cell: (row) => row.submitted },
    { key: "rr", header: "Sent back to them", numeric: true, cell: (row) => row.rejected_received },
    { key: "a", header: "Approved", numeric: true, cell: (row) => row.approved },
    { key: "rg", header: "Rejected", numeric: true, cell: (row) => row.rejected_given },
    { key: "po", header: "Posted", numeric: true, cell: (row) => row.posted },
    { key: "vo", header: "Voided", numeric: true, cell: (row) => row.voided },
  ];
  return (
    <DataTable
      caption="What each person did in the period"
      columns={columns}
      rows={report.data?.rows}
      getKey={(row) => row.user_id}
      loading={report.isPending}
      error={report.error}
      onRetry={() => report.refetch()}
      empty={{ title: "No people to show" }}
    />
  );
}
