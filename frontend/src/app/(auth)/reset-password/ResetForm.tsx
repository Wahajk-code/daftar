"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { messageFor } from "@/api/errors";
import { Button, ButtonLink } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { Banner } from "@/components/ui/States";
import styles from "../auth.module.css";

export const PASSWORD_HINT = "10 to 128 characters. A phrase of several words works well.";

export function ResetForm({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const mismatch = again !== "" && again !== password ? "The two passwords are different." : undefined;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== again) return;
    setPending(true);
    setError(null);
    try {
      await api("/auth/reset-password", { method: "POST", body: { token, new_password: password } });
      setDone(true);
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  }

  if (!token) {
    return (
      <>
        <div>
          <h1 className={styles.title}>This link is not complete</h1>
          <p className={styles.intro}>Open the link in your email again, or ask for a new one.</p>
        </div>
        <ButtonLink href="/forgot-password" variant="primary">
          Ask for a new link
        </ButtonLink>
      </>
    );
  }

  if (done) {
    return (
      <>
        <div>
          <h1 className={styles.title}>Password changed</h1>
          <p className={styles.intro}>You have been signed out everywhere. Sign in with your new password.</p>
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
        <h1 className={styles.title}>Choose a new password</h1>
        <p className={styles.intro}>This link works once.</p>
      </div>
      <form className={styles.form} onSubmit={submit} noValidate>
        {error ? (
          <Banner tone="negative" title="Could not change the password">
            {messageFor(error)}
          </Banner>
        ) : null}
        <TextField
          label="New password"
          type="password"
          name="new-password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          hint={PASSWORD_HINT}
          required
          autoFocus
        />
        <TextField
          label="Type it again"
          type="password"
          name="confirm-password"
          autoComplete="new-password"
          value={again}
          onChange={(event) => setAgain(event.target.value)}
          error={mismatch}
          required
        />
        <Button type="submit" variant="primary" className={styles.submit} pending={pending} disabled={!password || password !== again}>
          Change password
        </Button>
        <div className={styles.links}>
          <Link href="/login">Back to sign in</Link>
        </div>
      </form>
    </>
  );
}
