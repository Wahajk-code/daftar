"use client";

import { IconLock } from "@tabler/icons-react";
import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { useAction, usePage } from "@/api/queries";
import type { Period } from "@/api/types";
import { useMe } from "@/components/shell/MeContext";
import { Button } from "@/components/ui/Button";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { ConfirmDialog, Dialog } from "@/components/ui/Dialog";
import { TextField } from "@/components/ui/Field";
import { DateText, Instant } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { Banner } from "@/components/ui/States";
import { Tag } from "@/components/ui/Stamp";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";

export function Periods() {
  const me = useMe();
  const url = useUrlState();
  const isAdmin = me.role === "admin";
  const offset = Number(url.get("offset") || 0);
  const list = usePage<Period>("/periods", { sort: url.get("sort"), limit: PAGE_SIZE, offset });
  const [closing, setClosing] = useState(false);
  const [reopening, setReopening] = useState<Period | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const close = useAction<void, Period>({
    mutationFn: () => api<Period>("/periods/close", { method: "POST", body: { start_date: start, end_date: end } }),
    success: "Period closed",
    invalidate: [["list"], ["record"], ["report"]],
    onSuccess: () => setClosing(false),
  });
  const reopen = useAction<number, Period>({
    mutationFn: (id) => api<Period>(`/periods/${id}/reopen`, { method: "POST" }),
    success: "Period reopened",
    invalidate: [["list"]],
  });

  const columns: Column<Period>[] = [
    { key: "from", header: "From", sortKey: "start_date", cell: (row) => <DateText value={row.start_date} />, width: "130px" },
    { key: "to", header: "To", cell: (row) => <DateText value={row.end_date} />, width: "130px" },
    { key: "status", header: "Status", cell: (row) => <Tag tone={row.status === "closed" ? "negative" : "positive"}>{row.status === "closed" ? "Closed" : "Reopened"}</Tag>, width: "120px" },
    { key: "closed", header: "Closed", sortKey: "closed_at", cell: (row) => <Instant value={row.closed_at} /> },
    { key: "reopened", header: "Reopened", cell: (row) => (row.reopened_at ? <Instant value={row.reopened_at} /> : null) },
    ...(isAdmin
      ? [{ key: "actions", header: "Actions", width: "120px", cell: (row: Period) => (row.status === "closed" ? <Button small variant="secondary" onClick={() => setReopening(row)}>Reopen</Button> : null) } as Column<Period>]
      : []),
  ];
  const error = close.error instanceof ApiError ? close.error : null;

  function submit(event: FormEvent) {
    event.preventDefault();
    close.mutate();
  }

  return (
    <>
      <PageHeader
        title="Accounting periods"
        description="A closed period is locked: nothing dated inside it can be posted or voided. Admins close and reopen periods, and each change is recorded."
        actions={isAdmin ? <Button variant="primary" icon={<IconLock size={18} stroke={1.75} aria-hidden />} onClick={() => { close.reset(); setClosing(true); }}>Close a period</Button> : undefined}
      />
      <Panel flush>
        <DataTable
          caption="Closed accounting periods"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "-start_date"}
          onSort={(sort) => url.set({ sort })}
          empty={{ title: "No period has been closed", hint: "Every date is open for posting." }}
        />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={offset} onOffset={(next) => url.set({ offset: next })} noun="periods" /> : null}
      </Panel>

      <Dialog open={closing} onClose={() => !close.isPending && setClosing(false)} title="Close a period">
        <form onSubmit={submit} noValidate style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <p>Both dates are included. Once closed, no voucher dated in the period can be posted or voided until it is reopened.</p>
          {error && error.fields.length === 0 ? <Banner tone="negative" title="Could not close it">{messageFor(error)}</Banner> : null}
          <TextField label="First day" type="date" value={start} onChange={(event) => setStart(event.target.value)} error={error?.fieldMessage("start_date")} required />
          <TextField label="Last day" type="date" value={end} onChange={(event) => setEnd(event.target.value)} error={error?.fieldMessage("end_date")} required />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
            <Button onClick={() => setClosing(false)} disabled={close.isPending}>Cancel</Button>
            <Button type="submit" variant="primary" pending={close.isPending} disabled={!start || !end}>Close period</Button>
          </div>
        </form>
      </Dialog>
      <ConfirmDialog
        open={reopening !== null}
        onClose={() => setReopening(null)}
        title="Reopen this period"
        confirmLabel="Reopen period"
        danger
        onConfirm={() => (reopening ? reopen.mutateAsync(reopening.id) : Promise.resolve())}
      >
        Documents dated in this period can be posted and voided again until it is closed again.
      </ConfirmDialog>
    </>
  );
}
