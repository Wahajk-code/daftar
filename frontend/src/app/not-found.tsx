import Link from "next/link";

export default function NotFound() {
  return (
    <main style={{ minHeight: "100dvh", display: "grid", placeItems: "center", padding: "var(--space-5)" }}>
      <div style={{ maxWidth: 440, display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <h1>This page does not exist</h1>
        <p className="muted">The address may be mistyped, or the record may have been removed from your view.</p>
        <p>
          <Link href="/">Go to the home screen</Link>
        </p>
      </div>
    </main>
  );
}
