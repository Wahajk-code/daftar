"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { Banner } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { navigate } from "@/lib/navigate";
import { useCooldown } from "@/lib/use-cooldown";
import styles from "../auth.module.css";

export interface DemoAccount {
  email: string;
  name: string;
  role: string;
}

export const DEMO_PASSWORD = "daftar-demo-2026";

/** A path inside this site, or the home page: never an address on another site. */
function safeNext(value: string | undefined): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : "/";
}

export function LoginForm({ next, demo }: { next?: string; demo: DemoAccount[] }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const cooldown = useCooldown();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await api("/auth/login", { method: "POST", body: { email, password } });
      // A full navigation, so the server draws the first screen with the session that was just created.
      navigate(safeNext(next));
    } catch (caught) {
      setError(caught);
      if (caught instanceof ApiError && caught.code === "RATE_LIMITED" && caught.retryAfter) cooldown.start(caught.retryAfter);
      setPending(false);
    }
  }

  const waiting = cooldown.remaining > 0;

  return (
    <>
      <div>
        <h1 className={styles.title}>Sign in</h1>
        <p className={styles.intro}>Use the email address and password for your Daftar account.</p>
      </div>

      <form className={styles.form} onSubmit={submit} noValidate>
        {error ? (
          <Banner tone="negative" title={waiting ? "Too many attempts" : "Could not sign in"}>
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
        <TextField
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        <Button type="submit" variant="primary" className={styles.submit} pending={pending} disabled={waiting || !email || !password}>
          {waiting ? `Try again in ${cooldown.remaining}s` : "Sign in"}
        </Button>
        <div className={styles.links}>
          <Link href="/forgot-password">Forgot your password?</Link>
        </div>
      </form>

      {demo.length > 0 ? (
        <section className={styles.demo} aria-labelledby="demo-title">
          <h2 id="demo-title" className={styles.demoTitle}>
            Demonstration accounts
          </h2>
          <p className={styles.demoHint}>The password for all of them is {DEMO_PASSWORD}. Choose one to fill the form.</p>
          <ul className={styles.demoList}>
            {demo.map((account) => (
              <li key={account.email}>
                <button
                  type="button"
                  className={styles.demoButton}
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(DEMO_PASSWORD);
                  }}
                >
                  <span>
                    <span className={styles.demoName}>{account.name}</span>
                    <br />
                    <span className={styles.demoRole}>{account.email}</span>
                  </span>
                  <span className={styles.demoRole}>{account.role}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
