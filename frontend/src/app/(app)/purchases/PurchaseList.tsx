"use client";

import { IconPlus } from "@tabler/icons-react";
import Link from "next/link";
import { usePage, useVendors } from "@/api/queries";
import type { Purchase } from "@/api/types";
import { useMe } from "@/components/shell/MeContext";
import { ButtonLink } from "@/components/ui/Button";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { DateText, Identifier, Money } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { Stamp, Tag } from "@/components/ui/Stamp";
import { STATUS_OPTIONS } from "@/lib/documents";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";

export function PurchaseList() {
  const me = useMe();
  const url = useUrlState();
  const vendors = useVendors();
  const query = {
    status: url.get("status"),
    vendor_id: url.get("vendor_id"),
    registered: url.get("registered"),
    date_from: url.get("date_from"),
    date_to: url.get("date_to"),
    q: url.get("q"),
    sort: url.get("sort"),
    limit: PAGE_SIZE,
    offset: Number(url.get("offset") || 0),
  };
  const list = usePage<Purchase>("/purchases", query);
  const canWrite = me.role === "admin" || me.role === "accountant";

  const filters: FilterDef[] = [
    { key: "q", label: "Search", type: "search", placeholder: "Search descriptions and invoice numbers" },
    { key: "status", label: "Status", type: "select", options: STATUS_OPTIONS },
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
  ];

  const columns: Column<Purchase>[] = [
    { key: "date", header: "Dated", sortKey: "document_date", cell: (row) => <DateText value={row.document_date} />, width: "120px" },
    {
      key: "vendor",
      header: "Vendor",
      cell: (row) => (
        <Link href={`/purchases/${row.id}`} className="user-text">
          {row.vendor_name}
        </Link>
      ),
    },
    { key: "invoice", header: "Invoice", cell: (row) => (row.invoice_number ? <Identifier value={row.invoice_number} /> : <Tag>Memo</Tag>), width: "150px" },
    { key: "what", header: "For", cell: (row) => <span className="user-text">{row.description}</span> },
    { key: "gross", header: "Gross", numeric: true, sortKey: "gross_total", cell: (row) => <Money value={row.gross_total} />, width: "130px" },
    { key: "payable", header: "Payable", numeric: true, sortKey: "payable", cell: (row) => <Money value={row.payable} />, width: "130px" },
    { key: "status", header: "Status", sortKey: "status", cell: (row) => <Stamp status={row.status} />, width: "120px" },
  ];

  return (
    <>
      <PageHeader
        title="Purchases"
        description="Invoices and memos from vendors, with the tax worked out."
        actions={
          canWrite ? (
            <ButtonLink href="/purchases/new" variant="primary" icon={<IconPlus size={16} stroke={1.75} aria-hidden />}>
              New purchase
            </ButtonLink>
          ) : undefined
        }
      />
      <Panel flush>
        <ListFilters defs={filters} />
        <DataTable
          caption="Purchases"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "-document_date"}
          onSort={(sort) => url.set({ sort })}
          empty={{ title: "No purchases match", hint: "Change the filters, or add a purchase.", action: canWrite ? <ButtonLink href="/purchases/new">New purchase</ButtonLink> : undefined }}
        />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={query.offset} onOffset={(offset) => url.set({ offset })} noun="purchases" /> : null}
      </Panel>
    </>
  );
}
