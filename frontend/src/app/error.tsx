"use client";

import { useEffect } from "react";
import { Button, ButtonLink } from "@/components/ui/Button";

/** The last resort: something in the page broke. Say so, offer a retry, and keep the person's place. */
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <main style={{ minHeight: "60dvh", display: "grid", placeItems: "center", padding: "var(--space-5)" }}>
      <div role="alert" style={{ maxWidth: 480, display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <h1>Something went wrong on this page</h1>
        <p className="muted">Nothing you did was lost. Try again; if it keeps happening, tell an Admin and quote the reference below.</p>
        {error.digest ? <p className="ident faint">Reference {error.digest}</p> : null}
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button variant="primary" onClick={reset}>
            Try again
          </Button>
          <ButtonLink href="/">Go to the home screen</ButtonLink>
        </div>
      </div>
    </main>
  );
}
