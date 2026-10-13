"use client";

import { useCategories, usePage } from "@/api/queries";
import type { Expense } from "@/api/types";
import { useMe } from "@/components/shell/MeContext";
import { NewDocumentButton } from "@/components/shell/CreateModal";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { ExportButton } from "@/components/ui/ExportButton";
import { DateText, Money, TwoLine } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { Stamp, Tag } from "@/components/ui/Stamp";
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
    amount_min: url.get("amount_min"),
    amount_max: url.get("amount_max"),
    q: url.get("q"),
    mine: url.get("mine") === "true" ? true : undefined,
    sort: url.get("sort"),
    limit: PAGE_SIZE,
    offset: Number(url.get("offset") || 0),
  };
  const list = usePage<Expense>("/expenses", query);

  const filters: FilterDef[] = [
    { key: "q", label: "Search", type: "search", placeholder: "Search descriptions" },
    { key: "status", label: "Status", type: "select", options: STATUS_OPTIONS, quick: true },
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
    { key: "amount_min", label: "Amount from", type: "amount" },
    { key: "amount_max", label: "Amount up to", type: "amount" },
    ...(me.role !== "staff" ? ([{ key: "mine", label: "Only mine", type: "checkbox" }] as FilterDef[]) : []),
  ];

  const columns: Column<Expense>[] = [
    {
      key: "description",
      header: "Expense",
      primary: true,
      cell: (row) => <TwoLine title={row.description || row.category_name} sub={row.description ? row.category_name : null} />,
      title: (row) => row.description || row.category_name,
      maxWidth: "36ch",
    },
    { key: "date", header: "Dated", sortKey: "document_date", cell: (row) => <DateText value={row.document_date} />, width: "120px" },
    { key: "type", header: "Type", cell: (row) => <Tag tone={row.expense_type === "direct" ? "teal" : "violet"}>{row.expense_type === "direct" ? "Direct" : "Indirect"}</Tag>, width: "110px" },
    ...(me.role !== "staff"
      ? [{ key: "by", header: "By", cell: (row: Expense) => row.created_by_name, title: (row: Expense) => row.created_by_name, maxWidth: "18ch" } as Column<Expense>]
      : []),
    { key: "amount", header: "Amount", numeric: true, sortKey: "amount", cell: (row) => <Money value={row.amount} />, width: "140px" },
    { key: "status", header: "Status", sortKey: "status", cell: (row) => <Stamp status={row.status} />, width: "130px" },
  ];

  return (
    <>
      <PageHeader
        title="Expenses"
        description={me.role === "staff" ? "Your expenses and where each one stands." : "Every expense, whoever wrote it."}
        actions={
          <>
            {me.role !== "staff" ? (
              <ExportButton
                path="/reports/export/expenses"
                query={{
                  status: query.status,
                  expense_type: query.expense_type,
                  category_id: query.category_id,
                  date_from: query.date_from,
                  date_to: query.date_to,
                  amount_min: query.amount_min,
                  amount_max: query.amount_max,
                  q: query.q,
                }}
              />
            ) : null}
            <NewDocumentButton kind="expense">New expense</NewDocumentButton>
          </>
        }
      />
      <Panel flush>
        <ListFilters defs={filters} />
        <DataTable
          caption="Expenses"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          rowHref={(row) => `/expenses/${row.id}`}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "-document_date"}
          onSort={(sort) => url.set({ sort })}
          empty={{
            title: "No expenses match",
            hint: "Change the filters, or add an expense.",
            action: <NewDocumentButton kind="expense">New expense</NewDocumentButton>,
          }}
        />
        {list.data ? (
          <Pagination total={list.data.total} limit={PAGE_SIZE} offset={query.offset} onOffset={(offset) => url.set({ offset })} noun="expenses" />
        ) : null}
      </Panel>
    </>
  );
}
