"use client";

import { IconAlertTriangle, IconInbox, IconInfoCircle, IconCircleCheck } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { ApiError, messageFor } from "@/api/errors";
import { Button } from "./Button";
import styles from "./States.module.css";

/** An empty list says what to do next, not just that it is empty. */
export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={styles.state}>
      <IconInbox size={28} stroke={1.25} aria-hidden className={styles.icon} />
      <p className={styles.title}>{title}</p>
      {children ? <p className={`${styles.text} muted`}>{children}</p> : null}
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}

/** A failed load: what happened, the reference to quote, and a way to try again. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const reference = error instanceof ApiError ? error.correlationId : "";
  return (
    <div className={styles.state} role="alert">
      <IconAlertTriangle size={28} stroke={1.25} aria-hidden className={styles.problem} />
      <p className={styles.title}>This could not be loaded</p>
      <p className={`${styles.text} muted`}>{messageFor(error)}</p>
      {reference ? <p className={`${styles.reference} faint mono`}>Reference {reference}</p> : null}
      {onRetry ? (
        <div className={styles.action}>
          <Button onClick={onRetry}>Try again</Button>
        </div>
      ) : null}
    </div>
  );
}

export function LoadingBlock({ label = "Loading" }: { label?: string }) {
  return (
    <div className={styles.state} role="status" aria-live="polite">
      <span className={styles.bar} aria-hidden />
      <span className="sr-only">{label}</span>
    </div>
  );
}

/** Placeholder rows shaped like a table, so the page does not jump when the data arrives. */
export function SkeletonRows({ rows = 6, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <tbody aria-hidden>
      {Array.from({ length: rows }, (_, row) => (
        <tr key={row}>
          {Array.from({ length: columns }, (_, column) => (
            <td key={column}>
              <span className={styles.skeleton} style={{ width: `${40 + ((row * 7 + column * 13) % 50)}%` }} />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}

type Tone = "info" | "caution" | "negative" | "positive";

const BANNER_ICON = {
  info: IconInfoCircle,
  caution: IconAlertTriangle,
  negative: IconAlertTriangle,
  positive: IconCircleCheck,
} as const;

/** A message that belongs to the screen, for things a person should know before acting. */
export function Banner({
  tone = "info",
  title,
  children,
  actions,
}: {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  const Icon = BANNER_ICON[tone];
  return (
    <div className={`${styles.banner} ${styles[tone]}`} role={tone === "negative" ? "alert" : "status"}>
      <Icon size={20} stroke={1.5} aria-hidden className={styles.bannerIcon} />
      <div className={styles.bannerBody}>
        {title ? <p className={styles.bannerTitle}>{title}</p> : null}
        {children ? <div>{children}</div> : null}
      </div>
      {actions ? <div className={styles.bannerActions}>{actions}</div> : null}
    </div>
  );
}
