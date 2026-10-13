"use client";

import Link from "next/link";
import { usePage } from "@/api/queries";
import type { Voucher } from "@/api/types";
import { NewDocumentButton } from "@/components/shell/CreateModal";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { ExportButton } from "@/components/ui/ExportButton";
import { DateText, Money, TwoLine } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { Stamp, Tag } from "@/components/ui/Stamp";
import { STATUS_OPTIONS, VOUCHER_TYPES } from "@/lib/documents";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";

const TYPE_TONE = { PV: "teal", RV: "positive", JV: "violet" } as const;

export function VoucherList() {
  const url = useUrlState();
  const query = {
    voucher_type: url.get("voucher_type"),
    status: url.get("status"),
    date_from: url.get("date_from"),
    date_to: url.get("date_to"),
    amount_min: url.get("amount_min"),
    amount_max: url.get("amount_max"),
    q: url.get("q"),
    sort: url.get("sort"),
    limit: PAGE_SIZE,
    offset: Number(url.get("offset") || 0),
  };
  const list = usePage<Voucher>("/vouchers", query);

  const filters: FilterDef[] = [
    { key: "q", label: "Search", type: "search", placeholder: "Search numbers and narrations" },
    { key: "status", label: "Status", type: "select", options: STATUS_OPTIONS, quick: true },
    { key: "voucher_type", label: "Type", type: "select", options: VOUCHER_TYPES.map((type) => ({ value: type.value, label: type.label })) },
    { key: "date_from", label: "From", type: "date" },
    { key: "date_to", label: "To", type: "date" },
    { key: "amount_min", label: "Total from", type: "amount" },
    { key: "amount_max", label: "Total up to", type: "amount" },
  ];

  const columns: Column<Voucher>[] = [
    {
      key: "number",
      header: "Voucher",
      sortKey: "number",
      primary: true,
      cell: (row) => <TwoLine mono title={row.number ?? `${row.voucher_type} draft ${row.id}`} sub={row.description} />,
      title: (row) => row.number ?? `${row.voucher_type} draft ${row.id}`,
      maxWidth: "34ch",
    },
    { key: "type", header: "Type", cell: (row) => <Tag tone={TYPE_TONE[row.voucher_type]}>{row.voucher_type}</Tag>, width: "80px" },
    { key: "date", header: "Dated", sortKey: "document_date", cell: (row) => <DateText value={row.document_date} />, width: "120px" },
    { key: "by", header: "By", cell: (row) => row.created_by_name, title: (row) => row.created_by_name, maxWidth: "18ch" },
    {
      key: "source",
      header: "From",
      cell: (row) =>
        row.expense_id ? (
          <Link href={`/expenses/${row.expense_id}`}>Expense {row.expense_id}</Link>
        ) : row.purchase_id ? (
          <Link href={`/purchases/${row.purchase_id}`}>Purchase {row.purchase_id}</Link>
        ) : row.reversal_of_id ? (
          <Link href={`/vouchers/${row.reversal_of_id}`}>Reverses {row.reversal_of_number}</Link>
        ) : (
          <span className="faint">By hand</span>
        ),
      width: "150px",
    },
    { key: "total", header: "Total", numeric: true, cell: (row) => <Money value={row.total_debit} />, width: "140px" },
    { key: "status", header: "Status", sortKey: "status", cell: (row) => <Stamp status={row.status} />, width: "130px" },
  ];

  return (
    <>
      <PageHeader
        title="Vouchers"
        description="Every voucher balances: debits equal credits, always."
        actions={
          <>
            <ExportButton
              path="/reports/vouchers/csv"
              label="Export register CSV"
              query={{
                statuses: query.status ? [query.status] : undefined,
                voucher_type: query.voucher_type,
                date_from: query.date_from,
                date_to: query.date_to,
              }}
            />
            <NewDocumentButton kind="voucher">New voucher</NewDocumentButton>
          </>
        }
      />
      <Panel flush>
        <ListFilters defs={filters} />
        <DataTable
          caption="Vouchers"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          rowHref={(row) => `/vouchers/${row.id}`}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "-document_date"}
          onSort={(sort) => url.set({ sort })}
          empty={{ title: "No vouchers match", hint: "Change the filters, or add a voucher.", action: <NewDocumentButton kind="voucher">New voucher</NewDocumentButton> }}
        />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={query.offset} onOffset={(offset) => url.set({ offset })} noun="vouchers" /> : null}
      </Panel>
    </>
  );
}
