"use client";

import { usePage, useVendors } from "@/api/queries";
import type { Purchase } from "@/api/types";
import { NewDocumentButton } from "@/components/shell/CreateModal";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { DateText, Identifier, Money, TwoLine } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { Stamp, Tag } from "@/components/ui/Stamp";
import { STATUS_OPTIONS } from "@/lib/documents";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";

export function PurchaseList() {
  const url = useUrlState();
  const vendors = useVendors();
  const query = {
    status: url.get("status"),
    vendor_id: url.get("vendor_id"),
    registered: url.get("registered"),
    date_from: url.get("date_from"),
    date_to: url.get("date_to"),
    amount_min: url.get("amount_min"),
    amount_max: url.get("amount_max"),
    q: url.get("q"),
    sort: url.get("sort"),
    limit: PAGE_SIZE,
    offset: Number(url.get("offset") || 0),
  };
  const list = usePage<Purchase>("/purchases", query);

  const filters: FilterDef[] = [
    { key: "q", label: "Search", type: "search", placeholder: "Search descriptions and invoice numbers" },
    { key: "status", label: "Status", type: "select", options: STATUS_OPTIONS, quick: true },
    { key: "vendor_id", label: "Vendor", type: "select", options: (vendors.data ?? []).map((vendor) => ({ value: vendor.id, label: vendor.name })) },
    {
      key: "registered",
      label: "Registration",
      type: "select",
      options: [
        { value: "true", label: "Registered vendors" },
        { value: "false", label: "Not registered" },
      ],
    },
    { key: "date_from", label: "From", type: "date" },
    { key: "date_to", label: "To", type: "date" },
    { key: "amount_min", label: "Gross from", type: "amount" },
    { key: "amount_max", label: "Gross up to", type: "amount" },
  ];

  const columns: Column<Purchase>[] = [
    {
      key: "vendor",
      header: "Vendor",
      primary: true,
      cell: (row) => <TwoLine title={row.vendor_name} sub={row.description} />,
      title: (row) => row.vendor_name,
      maxWidth: "34ch",
    },
    { key: "date", header: "Dated", sortKey: "document_date", cell: (row) => <DateText value={row.document_date} />, width: "120px" },
    { key: "invoice", header: "Invoice", cell: (row) => (row.invoice_number ? <Identifier value={row.invoice_number} /> : <Tag tone="info">Memo</Tag>), width: "150px" },
    { key: "gross", header: "Gross", numeric: true, sortKey: "gross_total", cell: (row) => <Money value={row.gross_total} />, width: "140px" },
    { key: "payable", header: "Payable", numeric: true, sortKey: "payable", cell: (row) => <Money value={row.payable} />, width: "140px" },
    { key: "status", header: "Status", sortKey: "status", cell: (row) => <Stamp status={row.status} />, width: "130px" },
  ];

  return (
    <>
      <PageHeader
        title="Purchases"
        description="Invoices and memos from vendors, with the tax worked out."
        actions={<NewDocumentButton kind="purchase">New purchase</NewDocumentButton>}
      />
      <Panel flush>
        <ListFilters defs={filters} />
        <DataTable
          caption="Purchases"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          rowHref={(row) => `/purchases/${row.id}`}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "-document_date"}
          onSort={(sort) => url.set({ sort })}
          empty={{ title: "No purchases match", hint: "Change the filters, or add a purchase.", action: <NewDocumentButton kind="purchase">New purchase</NewDocumentButton> }}
        />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={query.offset} onOffset={(offset) => url.set({ offset })} noun="purchases" /> : null}
      </Panel>
    </>
  );
}
