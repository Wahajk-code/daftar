"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { Banner } from "@/components/ui/States";
import { useCooldown } from "@/lib/use-cooldown";
import styles from "../auth.module.css";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const cooldown = useCooldown();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api("/auth/forgot-password", { method: "POST", body: { email } });
      setSent(true);
    } catch (caught) {
      setError(caught);
      if (caught instanceof ApiError && caught.code === "RATE_LIMITED" && caught.retryAfter) cooldown.start(caught.retryAfter);
    } finally {
      setPending(false);
    }
  }

  const waiting = cooldown.remaining > 0;

  if (sent) {
    return (
      <>
        <div>
          <h1 className={styles.title}>Check your email</h1>
          <p className={styles.intro}>
            If that address has a Daftar account, we have sent a link to choose a new password. The link works once and
            expires in 30 minutes.
          </p>
        </div>
        <div className={styles.links}>
          <Link href="/login">Back to sign in</Link>
        </div>
      </>
    );
  }

  return (
    <>
      <div>
        <h1 className={styles.title}>Reset your password</h1>
        <p className={styles.intro}>Enter your email address and we will send you a link to choose a new password.</p>
      </div>
      <form className={styles.form} onSubmit={submit} noValidate>
        {error ? (
          <Banner tone="negative" title={waiting ? "Too many attempts" : "Could not send the link"}>
            {waiting ? `Wait ${cooldown.remaining} seconds, then try again.` : messageFor(error)}
          </Banner>
        ) : null}
        <TextField
          label="Email"
          type="email"
          name="email"
          autoComplete="username"
          inputMode="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          autoFocus
        />
        <Button type="submit" variant="primary" className={styles.submit} pending={pending} disabled={waiting || !email}>
          {waiting ? `Try again in ${cooldown.remaining}s` : "Send the link"}
        </Button>
        <div className={styles.links}>
          <Link href="/login">Back to sign in</Link>
        </div>
      </form>
    </>
  );
}
