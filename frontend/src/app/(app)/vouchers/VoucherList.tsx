"use client";

import { IconPlus } from "@tabler/icons-react";
import Link from "next/link";
import { usePage } from "@/api/queries";
import type { Voucher } from "@/api/types";
import { useMe } from "@/components/shell/MeContext";
import { ButtonLink } from "@/components/ui/Button";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { DateText, Identifier, Money } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { Stamp } from "@/components/ui/Stamp";
import { STATUS_OPTIONS, VOUCHER_TYPES } from "@/lib/documents";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";

export function VoucherList() {
  const me = useMe();
  const url = useUrlState();
  const query = {
    voucher_type: url.get("voucher_type"),
    status: url.get("status"),
    date_from: url.get("date_from"),
    date_to: url.get("date_to"),
    q: url.get("q"),
    sort: url.get("sort"),
    limit: PAGE_SIZE,
    offset: Number(url.get("offset") || 0),
  };
  const list = usePage<Voucher>("/vouchers", query);
  const canWrite = me.role === "admin" || me.role === "accountant";

  const filters: FilterDef[] = [
    { key: "q", label: "Search", type: "search", placeholder: "Search numbers and narrations" },
    { key: "voucher_type", label: "Type", type: "select", options: VOUCHER_TYPES.map((type) => ({ value: type.value, label: type.label })) },
    { key: "status", label: "Status", type: "select", options: STATUS_OPTIONS },
    { key: "date_from", label: "From", type: "date" },
    { key: "date_to", label: "To", type: "date" },
  ];

  const columns: Column<Voucher>[] = [
    {
      key: "number",
      header: "Number",
      sortKey: "number",
      cell: (row) => (
        <Link href={`/vouchers/${row.id}`}>
          <Identifier value={row.number ?? `${row.voucher_type} draft ${row.id}`} voided={row.status === "void"} />
        </Link>
      ),
      width: "170px",
    },
    { key: "date", header: "Dated", sortKey: "document_date", cell: (row) => <DateText value={row.document_date} />, width: "120px" },
    { key: "narration", header: "Narration", cell: (row) => <span className="user-text">{row.description}</span> },
    { key: "by", header: "By", cell: (row) => row.created_by_name },
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
          <span className="faint">Entered by hand</span>
        ),
      width: "150px",
    },
    { key: "total", header: "Total", numeric: true, cell: (row) => <Money value={row.total_debit} />, width: "130px" },
    { key: "status", header: "Status", sortKey: "status", cell: (row) => <Stamp status={row.status} />, width: "120px" },
  ];

  return (
    <>
      <PageHeader
        title="Vouchers"
        description="Every voucher balances: debits equal credits, always."
        actions={
          canWrite ? (
            <ButtonLink href="/vouchers/new" variant="primary" icon={<IconPlus size={16} stroke={1.75} aria-hidden />}>
              New voucher
            </ButtonLink>
          ) : undefined
        }
      />
      <Panel flush>
        <ListFilters defs={filters} />
        <DataTable
          caption="Vouchers"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "-document_date"}
          onSort={(sort) => url.set({ sort })}
          empty={{ title: "No vouchers match", hint: "Change the filters, or add a voucher.", action: canWrite ? <ButtonLink href="/vouchers/new">New voucher</ButtonLink> : undefined }}
        />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={query.offset} onOffset={(offset) => url.set({ offset })} noun="vouchers" /> : null}
      </Panel>
    </>
  );
}
