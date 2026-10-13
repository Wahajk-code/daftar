"use client";

import { IconBuildingBank } from "@tabler/icons-react";
import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { REFERENCE_ROOT, useAction } from "@/api/queries";
import type { Vendor } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { TextField } from "@/components/ui/Field";
import { Banner } from "@/components/ui/States";

/**
 * Changing where a vendor is paid is the classic route for a payment fraud, so it asks for the person's own password again
 * and the vendor's address book is told. The account number is stored encrypted and shown masked.
 */
export function BankAccountButton({ vendor }: { vendor: Vendor }) {
  const [open, setOpen] = useState(false);
  const [number, setNumber] = useState("");
  const [bank, setBank] = useState(vendor.bank_name ?? "");
  const [password, setPassword] = useState("");

  const change = useAction<void, Vendor>({
    mutationFn: () =>
      api<Vendor>(`/vendors/${vendor.id}/bank-account`, {
        method: "POST",
        version: vendor.version,
        body: { account_number: number, bank_name: bank || null, current_password: password },
      }),
    success: "Bank account changed",
    invalidate: [["list"], [REFERENCE_ROOT]],
    onSuccess: () => {
      setOpen(false);
      setNumber("");
      setPassword("");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    change.mutate();
  }

  const error = change.error instanceof ApiError ? change.error : null;
  return (
    <>
      <Button small variant="quiet" icon={<IconBuildingBank size={14} stroke={1.75} aria-hidden />} onClick={() => { change.reset(); setPassword(""); setOpen(true); }}>
        Bank account
      </Button>
      <Dialog open={open} onClose={() => !change.isPending && setOpen(false)} title={`Bank account for ${vendor.name}`}>
        <form onSubmit={submit} noValidate style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <p className="muted">Now: {vendor.bank_account_masked ?? "no account on record"}. Everyone with access to vendors is emailed when it changes.</p>
          {error && error.fields.length === 0 ? <Banner tone="negative" title="Could not change it">{messageFor(error)}</Banner> : null}
          <TextField label="New account number or IBAN" value={number} onChange={(event) => setNumber(event.target.value)} error={error?.fieldMessage("account_number")} required autoFocus />
          <TextField label="Bank" value={bank} onChange={(event) => setBank(event.target.value)} error={error?.fieldMessage("bank_name")} />
          <TextField label="Your password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} error={error?.fieldMessage("current_password")} hint="Needed again for this change." required />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
            <Button onClick={() => setOpen(false)} disabled={change.isPending}>Cancel</Button>
            <Button type="submit" variant="primary" pending={change.isPending} disabled={!number || !password}>Change account</Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
