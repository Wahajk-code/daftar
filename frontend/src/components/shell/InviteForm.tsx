"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { useAction } from "@/api/queries";
import type { Invite, Role } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { Requirements } from "@/components/ui/Requirements";
import { Banner } from "@/components/ui/States";
import { ROLE_OPTIONS } from "./roles";
import styles from "./InviteForm.module.css";

/** Invite someone by email and choose their role. Used in the modal that the New menu and the Users screen both open. */
export function InviteForm({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("staff");

  const invite = useAction<void, Invite>({
    mutationFn: () => api<Invite>("/invites", { method: "POST", body: { email, role } }),
    success: "Invitation sent",
    invalidate: [["list"]],
    onSuccess: () => {
      onClose();
      router.push("/users?tab=invites");
    },
  });
  const error = invite.error instanceof ApiError ? invite.error : null;
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const emailProblem = email.trim() !== "" && !emailOk ? "Enter a full address, such as name@company.pk." : undefined;

  return (
    <form
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        invite.mutate();
      }}
      className={styles.form}
      noValidate
    >
      {error && error.fields.length === 0 ? (
        <Banner tone="negative" title="Could not send it">
          {messageFor(error)}
        </Banner>
      ) : null}
      <TextField label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} error={emailProblem ?? error?.fieldMessage("email")} required autoFocus />
      <SelectField label="Role" value={role} onChange={(event) => setRole(event.target.value as Role)} options={ROLE_OPTIONS.map((item) => ({ value: item.value, label: item.label }))} hint={ROLE_OPTIONS.find((item) => item.value === role)?.about} />
      <p className="muted">The link works once and expires in 7 days. Sending it again cancels the earlier one.</p>
      <div className={styles.actions}>
        <Requirements items={emailOk ? [] : ["A valid email address"]} />
        <Button onClick={onClose} disabled={invite.isPending}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" pending={invite.isPending} disabled={!emailOk}>
          Send invitation
        </Button>
      </div>
    </form>
  );
}
