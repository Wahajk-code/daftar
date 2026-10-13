"use client";

import { IconMailForward, IconPlus } from "@tabler/icons-react";
import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { useAction, usePage } from "@/api/queries";
import type { Invite, Role, User } from "@/api/types";
import { useMe } from "@/components/shell/MeContext";
import { Button } from "@/components/ui/Button";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { ConfirmDialog, Dialog } from "@/components/ui/Dialog";
import { SelectField, TextField } from "@/components/ui/Field";
import { Instant } from "@/components/ui/Format";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { Banner } from "@/components/ui/States";
import { Tag } from "@/components/ui/Stamp";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";
import styles from "./Users.module.css";

const ROLES: Array<{ value: Role; label: string; about: string }> = [
  { value: "admin", label: "Admin", about: "Manages people and roles, closes periods, reads the audit log, and can do everything else." },
  { value: "accountant", label: "Accountant", about: "Keeps the books: master data, tax rates, purchases, vouchers, posting and voiding." },
  { value: "approver", label: "Approver", about: "Reads everything and approves or rejects documents other people wrote." },
  { value: "staff", label: "Staff", about: "Writes and sends their own expenses with receipts." },
];

const roleLabel = (role: Role) => ROLES.find((item) => item.value === role)?.label ?? role;

function UsersTable() {
  const me = useMe();
  const url = useUrlState();
  const offset = Number(url.get("offset") || 0);
  const list = usePage<User>("/users", { q: url.get("q"), role: url.get("role"), is_active: url.get("is_active"), sort: url.get("sort"), limit: PAGE_SIZE, offset });
  const [roleFor, setRoleFor] = useState<User | null>(null);
  const [role, setRole] = useState<Role>("staff");
  const [resetFor, setResetFor] = useState<User | null>(null);

  const changeRole = useAction<void, User>({
    mutationFn: () => api<User>(`/users/${roleFor?.id}/role`, { method: "POST", body: { role } }),
    success: "Role changed",
    invalidate: [["list"]],
    onSuccess: () => setRoleFor(null),
  });
  const toggle = useAction<User, User>({
    mutationFn: (user) => api<User>(`/users/${user.id}/${user.is_active ? "deactivate" : "reactivate"}`, { method: "POST" }),
    success: (user) => (user.is_active ? "User reactivated" : "User deactivated"),
    invalidate: [["list"]],
  });
  const reset = useAction<User, unknown>({
    mutationFn: (user) => api(`/users/${user.id}/reset-password`, { method: "POST" }),
    success: "Reset link sent",
    invalidate: [],
  });

  const filters: FilterDef[] = [
    { key: "q", label: "Search", type: "search", placeholder: "Search names and emails" },
    { key: "role", label: "Role", type: "select", options: ROLES.map((item) => ({ value: item.value, label: item.label })) },
    { key: "is_active", label: "Status", type: "select", options: [{ value: "true", label: "Active" }, { value: "false", label: "Deactivated" }] },
  ];
  const columns: Column<User>[] = [
    { key: "name", header: "Name", sortKey: "full_name", cell: (row) => <span className="user-text">{row.full_name}</span> },
    { key: "email", header: "Email", sortKey: "email", cell: (row) => row.email },
    { key: "role", header: "Role", sortKey: "role", cell: (row) => roleLabel(row.role), width: "120px" },
    { key: "status", header: "Status", cell: (row) => <Tag tone={row.is_active ? "positive" : "neutral"}>{row.is_active ? "Active" : "Deactivated"}</Tag>, width: "120px" },
    { key: "since", header: "Joined", cell: (row) => <Instant value={row.created_at} />, width: "170px" },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      width: "330px",
      cell: (row) => (
        <span className={styles.rowActions}>
          <Button small variant="quiet" disabled={row.id === me.id} onClick={() => { changeRole.reset(); setRole(row.role); setRoleFor(row); }}>Change role</Button>
          <Button small variant="quiet" disabled={!row.is_active} onClick={() => setResetFor(row)}>Send reset link</Button>
          <Button small variant="quiet" disabled={row.id === me.id} pending={toggle.isPending && toggle.variables?.id === row.id} onClick={() => toggle.mutate(row)}>
            {row.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        </span>
      ),
    },
  ];
  const error = changeRole.error instanceof ApiError ? changeRole.error : null;

  return (
    <>
      <Panel flush>
        <ListFilters defs={filters} />
        <DataTable
          caption="Users"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "full_name"}
          onSort={(sort) => url.set({ sort })}
          empty={{ title: "No users match", hint: "Change the filters." }}
        />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={offset} onOffset={(next) => url.set({ offset: next })} noun="users" /> : null}
      </Panel>
      <Dialog open={roleFor !== null} onClose={() => !changeRole.isPending && setRoleFor(null)} title={`Change the role of ${roleFor?.full_name ?? ""}`}>
        <form onSubmit={(event) => { event.preventDefault(); changeRole.mutate(); }} className={styles.form}>
          {error ? <Banner tone="negative" title="Could not change it">{messageFor(error)}</Banner> : null}
          <SelectField label="Role" value={role} onChange={(event) => setRole(event.target.value as Role)} options={ROLES.map((item) => ({ value: item.value, label: item.label }))} hint={ROLES.find((item) => item.value === role)?.about} />
          <p className="muted">They are signed out everywhere, and the new role applies at once.</p>
          <div className={styles.actions}>
            <Button onClick={() => setRoleFor(null)} disabled={changeRole.isPending}>Cancel</Button>
            <Button type="submit" variant="primary" pending={changeRole.isPending}>Change role</Button>
          </div>
        </form>
      </Dialog>
      <ConfirmDialog open={resetFor !== null} onClose={() => setResetFor(null)} title="Send a password reset link" confirmLabel="Send the link" onConfirm={() => (resetFor ? reset.mutateAsync(resetFor) : Promise.resolve())}>
        {resetFor?.full_name} is emailed a link to choose a new password. You never see or set the password yourself.
      </ConfirmDialog>
    </>
  );
}

function InvitesTable() {
  const url = useUrlState();
  const offset = Number(url.get("offset") || 0);
  const list = usePage<Invite>("/invites", { sort: url.get("sort"), limit: PAGE_SIZE, offset });
  const [inviting, setInviting] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("staff");
  const [revoking, setRevoking] = useState<Invite | null>(null);

  const invite = useAction<void, Invite>({
    mutationFn: () => api<Invite>("/invites", { method: "POST", body: { email, role } }),
    success: "Invitation sent",
    invalidate: [["list"]],
    onSuccess: () => { setInviting(false); setEmail(""); },
  });
  const resend = useAction<Invite, Invite>({ mutationFn: (item) => api<Invite>(`/invites/${item.id}/resend`, { method: "POST" }), success: "Invitation sent again", invalidate: [["list"]] });
  const revoke = useAction<Invite, unknown>({ mutationFn: (item) => api(`/invites/${item.id}/revoke`, { method: "POST" }), success: "Invitation cancelled", invalidate: [["list"]] });
  const error = invite.error instanceof ApiError ? invite.error : null;

  const columns: Column<Invite>[] = [
    { key: "email", header: "Email", cell: (row) => row.email },
    { key: "role", header: "Role", cell: (row) => roleLabel(row.role), width: "120px" },
    { key: "status", header: "Status", cell: (row) => <Tag tone={row.status === "pending" ? "caution" : row.status === "accepted" ? "positive" : "neutral"}>{row.status}</Tag>, width: "120px" },
    { key: "sent", header: "Sent", sortKey: "created_at", cell: (row) => <Instant value={row.created_at} />, width: "170px" },
    { key: "expires", header: "Expires", cell: (row) => <Instant value={row.expires_at} />, width: "170px" },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      width: "220px",
      cell: (row) =>
        row.status === "pending" || row.status === "expired" ? (
          <span className={styles.rowActions}>
            <Button small variant="quiet" icon={<IconMailForward size={14} stroke={1.75} aria-hidden />} pending={resend.isPending && resend.variables?.id === row.id} onClick={() => resend.mutate(row)}>Send again</Button>
            {row.status === "pending" ? <Button small variant="quiet" onClick={() => setRevoking(row)}>Cancel</Button> : null}
          </span>
        ) : null,
    },
  ];

  return (
    <>
      <Panel
        flush
        title="Invitations"
        actions={<Button variant="primary" icon={<IconPlus size={16} stroke={1.75} aria-hidden />} onClick={() => { invite.reset(); setInviting(true); }}>Invite someone</Button>}
      >
        <DataTable
          caption="Invitations"
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || "-created_at"}
          onSort={(sort) => url.set({ sort })}
          empty={{ title: "No invitations yet", hint: "Invite a person by email and choose their role. They set their own name and password." }}
        />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={offset} onOffset={(next) => url.set({ offset: next })} noun="invitations" /> : null}
      </Panel>
      <Dialog open={inviting} onClose={() => !invite.isPending && setInviting(false)} title="Invite someone">
        <form onSubmit={(event: FormEvent) => { event.preventDefault(); invite.mutate(); }} className={styles.form} noValidate>
          {error && error.fields.length === 0 ? <Banner tone="negative" title="Could not send it">{messageFor(error)}</Banner> : null}
          <TextField label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} error={error?.fieldMessage("email")} required autoFocus />
          <SelectField label="Role" value={role} onChange={(event) => setRole(event.target.value as Role)} options={ROLES.map((item) => ({ value: item.value, label: item.label }))} hint={ROLES.find((item) => item.value === role)?.about} />
          <p className="muted">The link works once and expires in 7 days. Sending it again cancels the earlier one.</p>
          <div className={styles.actions}>
            <Button onClick={() => setInviting(false)} disabled={invite.isPending}>Cancel</Button>
            <Button type="submit" variant="primary" pending={invite.isPending} disabled={!email}>Send invitation</Button>
          </div>
        </form>
      </Dialog>
      <ConfirmDialog open={revoking !== null} onClose={() => setRevoking(null)} title="Cancel this invitation" confirmLabel="Cancel the invitation" danger onConfirm={() => (revoking ? revoke.mutateAsync(revoking) : Promise.resolve())}>
        The link in the email to {revoking?.email} stops working.
      </ConfirmDialog>
    </>
  );
}

export function Users() {
  const url = useUrlState();
  const tab = url.get("tab") === "invites" ? "invites" : "users";
  return (
    <>
      <PageHeader title="Users and invites" description="Admins manage people and what each role may do. Nobody here ever sees or sets a password." />
      <div className={styles.tabs} role="tablist" aria-label="People">
        <button type="button" role="tab" aria-selected={tab === "users"} onClick={() => url.set({ tab: null, offset: null })}>People</button>
        <button type="button" role="tab" aria-selected={tab === "invites"} onClick={() => url.set({ tab: "invites", offset: null })}>Invitations</button>
      </div>
      {tab === "users" ? <UsersTable /> : <InvitesTable />}
    </>
  );
}
