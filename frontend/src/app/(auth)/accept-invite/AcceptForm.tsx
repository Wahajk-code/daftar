"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { messageFor } from "@/api/errors";
import type { components } from "@/api/schema";
import { Button, ButtonLink } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { Banner, LoadingBlock } from "@/components/ui/States";
import { PASSWORD_HINT } from "../reset-password/ResetForm";
import styles from "../auth.module.css";

type Invite = components["schemas"]["InviteInspectRead"];

const ROLE_TEXT: Record<string, string> = {
  admin: "an Admin",
  accountant: "an Accountant",
  approver: "an Approver",
  staff: "a member of Staff",
};

export function AcceptForm({ token }: { token: string }) {
  const [invite, setInvite] = useState<Invite | null>(null);
  const [inspectError, setInspectError] = useState<unknown>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api<Invite>("/auth/invites/inspect", { method: "POST", body: { token } })
      .then((found) => !cancelled && setInvite(found))
      .catch((caught) => !cancelled && setInspectError(caught));
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api("/auth/invites/accept", { method: "POST", body: { token, full_name: name, password } });
      setDone(true);
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  }

  if (!token || inspectError) {
    return (
      <>
        <div>
          <h1 className={styles.title}>This invitation cannot be used</h1>
          <p className={styles.intro}>
            {token ? messageFor(inspectError) : "The link is incomplete."} Ask an Admin to send you a new one.
          </p>
        </div>
        <ButtonLink href="/login">Go to sign in</ButtonLink>
      </>
    );
  }

  if (!invite) return <LoadingBlock label="Checking your invitation" />;

  if (done) {
    return (
      <>
        <div>
          <h1 className={styles.title}>Your account is ready</h1>
          <p className={styles.intro}>Sign in with {invite.email} and the password you just chose.</p>
        </div>
        <ButtonLink href="/login" variant="primary">
          Go to sign in
        </ButtonLink>
      </>
    );
  }

  return (
    <>
      <div>
        <h1 className={styles.title}>Join Daftar</h1>
        <p className={styles.intro}>
          You have been invited as {ROLE_TEXT[invite.role] ?? invite.role}. Your email address is {invite.email}.
        </p>
      </div>
      <form className={styles.form} onSubmit={submit} noValidate>
        {error ? (
          <Banner tone="negative" title="Could not create the account">
            {messageFor(error)}
          </Banner>
        ) : null}
        <TextField
          label="Your name"
          name="name"
          autoComplete="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          autoFocus
        />
        <TextField
          label="Choose a password"
          type="password"
          name="new-password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          hint={PASSWORD_HINT}
          required
        />
        <Button type="submit" variant="primary" className={styles.submit} pending={pending} disabled={!name.trim() || !password}>
          Create account
        </Button>
      </form>
    </>
  );
}
