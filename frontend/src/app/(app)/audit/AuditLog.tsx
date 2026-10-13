"use client";

import Link from "next/link";
import { usePage } from "@/api/queries";
import type { components } from "@/api/schema";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { Instant } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";
import styles from "./AuditLog.module.css";

type Event = components["schemas"]["AuditEventRead"];

const ENTITIES = ["expense", "purchase", "voucher", "vendor", "account", "category", "cost_center", "project", "period", "posting_account", "tax_rule", "accounting_settings", "attachment", "invite", "user", "report"];

const LINKS: Record<string, string> = { expense: "expenses", purchase: "purchases", voucher: "vouchers" };

function Changes({ before, after }: { before: Event["before"]; after: Event["after"] }) {
  const keys = [...new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])];
  if (keys.length === 0) return <span className="faint">No values recorded</span>;
  const show = (value: unknown) => (value === null || value === undefined ? "none" : typeof value === "object" ? JSON.stringify(value) : String(value));
  return (
    <details className={styles.details}>
      <summary>{keys.length} value{keys.length === 1 ? "" : "s"}</summary>
      <dl>
        {keys.map((key) => (
          <div key={key}>
            <dt className="ident">{key}</dt>
            <dd>
              {before && key in before ? <span className={styles.was}>{show(before[key])}</span> : null}
              {before && key in before && after && key in after ? " to " : null}
              {after && key in after ? <span className={styles.now}>{show(after[key])}</span> : null}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

export function AuditLog() {
  const url = useUrlState();
  const offset = Number(url.get("offset") || 0);
  const list = usePage<Event>("/audit", {
    entity_type: url.get("entity_type"),
    action: url.get("action"),
    date_from: url.get("date_from"),
    date_to: url.get("date_to"),
    actor_id: url.get("actor_id"),
    limit: PAGE_SIZE,
    offset,
  });

  const filters: FilterDef[] = [
    { key: "action", label: "Action", type: "search", placeholder: "Part of an action, such as posted" },
    { key: "entity_type", label: "Record", type: "select", options: ENTITIES.map((value) => ({ value, label: value.replace("_", " ") })) },
    { key: "date_from", label: "From", type: "date" },
    { key: "date_to", label: "To", type: "date" },
  ];
  const columns: Column<Event>[] = [
    { key: "when", header: "When", cell: (row) => <Instant value={row.occurred_at} />, width: "180px" },
    { key: "who", header: "Who", cell: (row) => row.actor_name ?? <span className="faint">No signed-in user</span>, width: "190px" },
    { key: "action", header: "Action", cell: (row) => <span className="ident">{row.action}</span>, width: "230px" },
    {
      key: "record",
      header: "Record",
      width: "150px",
      cell: (row) =>
        row.entity_id === null ? (
          row.entity_type
        ) : LINKS[row.entity_type] ? (
          <Link href={`/${LINKS[row.entity_type]}/${row.entity_id}`}>
            {row.entity_type} {row.entity_id}
          </Link>
        ) : (
          `${row.entity_type} ${row.entity_id}`
        ),
    },
    { key: "changes", header: "What changed", cell: (row) => <Changes before={row.before} after={row.after} /> },
  ];

  return (
    <>
      <PageHeader title="Audit log" description="Who did what, and when. Entries are only ever added: nobody can change or remove one." />
      <Panel flush>
        <ListFilters defs={filters} />
        <DataTable caption="Audit log" columns={columns} rows={list.data?.items} getKey={(row) => row.id} loading={list.isPending} error={list.error} onRetry={() => list.refetch()} empty={{ title: "No entries match", hint: "Change the filters." }} />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={offset} onOffset={(next) => url.set({ offset: next })} noun="entries" /> : null}
      </Panel>
    </>
  );
}
