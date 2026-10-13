"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { useAction } from "@/api/queries";
import { useMe } from "@/components/shell/MeContext";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { Facts, PageHeader, Panel } from "@/components/ui/Layout";
import { Banner } from "@/components/ui/States";
import { Instant } from "@/components/ui/Format";
import { navigate } from "@/lib/navigate";

const ROLE_TEXT = { admin: "Admin", accountant: "Accountant", approver: "Approver", staff: "Staff" } as const;

export function Profile() {
  const me = useMe();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");

  const change = useAction<void, unknown>({
    mutationFn: () => api("/me/password", { method: "POST", body: { current_password: current, new_password: next } }),
    success: "Password changed. Sign in again.",
    invalidate: [],
    onSuccess: () => window.setTimeout(() => navigate("/login"), 1200),
  });
  const error = change.error instanceof ApiError ? change.error : null;
  const mismatch = again !== "" && again !== next ? "The two passwords are different." : undefined;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (next === again) change.mutate();
  }

  return (
    <>
      <PageHeader title="Your account" description="Who you are in Daftar, and your password." />
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel title="You">
          <Facts
            items={[
              { label: "Name", value: me.full_name },
              { label: "Email", value: me.email },
              { label: "Role", value: ROLE_TEXT[me.role] },
              { label: "Joined", value: <Instant value={me.created_at} /> },
              { label: "Times are shown in", value: me.display_timezone },
            ]}
          />
        </Panel>
        <Panel title="Change your password">
          <form onSubmit={submit} noValidate style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", maxWidth: 420 }}>
            <p className="muted">Changing it signs you out of every device, this one included.</p>
            {error && error.fields.length === 0 ? <Banner tone="negative" title="Could not change it">{messageFor(error)}</Banner> : null}
            <TextField label="Current password" type="password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} error={error?.code === "REAUTH_FAILED" ? messageFor(error) : undefined} required />
            <TextField label="New password" type="password" autoComplete="new-password" value={next} onChange={(event) => setNext(event.target.value)} hint="10 to 128 characters. A phrase of several words works well." error={error?.fieldMessage("new_password")} required />
            <TextField label="Type it again" type="password" autoComplete="new-password" value={again} onChange={(event) => setAgain(event.target.value)} error={mismatch} required />
            <div>
              <Button type="submit" variant="primary" pending={change.isPending} disabled={!current || !next || next !== again}>
                Change password
              </Button>
            </div>
          </form>
        </Panel>
      </div>
    </>
  );
}
