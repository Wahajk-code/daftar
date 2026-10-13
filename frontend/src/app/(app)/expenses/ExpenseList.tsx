"use client";

import { IconPlus } from "@tabler/icons-react";
import Link from "next/link";
import { useCategories, usePage } from "@/api/queries";
import type { Expense } from "@/api/types";
import { useMe } from "@/components/shell/MeContext";
import { ButtonLink } from "@/components/ui/Button";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { DateText, Money } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { Stamp } from "@/components/ui/Stamp";
import { STATUS_OPTIONS } from "@/lib/documents";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";

export function ExpenseList() {
  const me = useMe();
  const url = useUrlState();
  const categories = useCategories();

  const query = {
    status: url.get("status"),
    expense_type: url.get("expense_type"),
    category_id: url.get("category_id"),
    date_from: url.get("date_from"),
    date_to: url.get("date_to"),
    q: url.get("q"),
    mine: url.get("mine") === "true" ? true : undefined,
    sort: url.get("sort"),
    limit: PAGE_SIZE,
    offset: Number(url.get("offset") || 0),
  };
  const list = usePage<Expense>("/expenses", query);

  const filters: FilterDef[] = [
    { key: "q", label: "Search", type: "search", placeholder: "Search descriptions" },
    { key: "status", label: "Status", type: "select", options: STATUS_OPTIONS },
    {
      key: "expense_type",
      label: "Type",
      type: "select",
      options: [
        { value: "direct", label: "Direct" },
        { value: "indirect", label: "Indirect" },
      ],
    },
    {
      key: "category_id",
      label: "Category",
      type: "select",
      options: (categories.data ?? []).map((category) => ({ value: category.id, label: category.name })),
    },
    { key: "date_from", label: "From", type: "date" },
    { key: "date_to", label: "To", type: "date" },
    ...(me.role !== "staff" ? ([{ key: "mine", label: "Only mine", type: "checkbox" }] as FilterDef[]) : []),
  ];

  const columns: Column<Expense>[] = [
    { key: "date", header: "Dated", sortKey: "document_date", cell: (row) => <DateText value={row.document_date} />, width: "120px" },
    {
      key: "description",
      header: "Description",
      cell: (row) => (
        <Link href={`/expenses/${row.id}`} className="user-text">
          {row.description || row.category_name}
        </Link>
      ),
    },
    { key: "category", header: "Category", cell: (row) => row.category_name },
    { key: "type", header: "Type", cell: (row) => (row.expense_type === "direct" ? "Direct" : "Indirect"), width: "90px" },
    ...(me.role !== "staff" ? [{ key: "by", header: "By", cell: (row: Expense) => row.created_by_name } as Column<Expense>] : []),
    { key: "amount", header: "Amount", numeric: true, sortKey: "amount", cell: (row) => <Money value={row.amount} />, width: "130px" },
    { key: "status", header: "Status", sortKey: "status", cell: (row) => <Stamp status={row.status} />, width: "120px" },
  ];

  return (
    <>
      <PageHeader
        title="Expenses"
        description={me.role === "staff" ? "Your expenses and where each one stands." : "Every expense, whoever wrote it."}
        actions={
          me.role !== "approver" ? (
            <ButtonLink href="/expenses/new" variant="primary" icon={<IconPlus size={16} stroke={1.75} aria-hidden />}>
              New expense
            </ButtonLink>
          ) : undefined
        }
      />
      <Panel flush>
        <ListFilters defs={filters} />
        <DataTable
          caption="Expenses"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "-document_date"}
          onSort={(sort) => url.set({ sort })}
          empty={{
            title: "No expenses match",
            hint: "Change the filters, or add an expense.",
            action: me.role !== "approver" ? <ButtonLink href="/expenses/new">New expense</ButtonLink> : undefined,
          }}
        />
        {list.data ? (
          <Pagination total={list.data.total} limit={PAGE_SIZE} offset={query.offset} onOffset={(offset) => url.set({ offset })} noun="expenses" />
        ) : null}
      </Panel>
    </>
  );
}
