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
      <IconInbox size={30} stroke={1.25} aria-hidden className={styles.icon} />
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
      <IconAlertTriangle size={30} stroke={1.25} aria-hidden className={styles.problem} />
      <p className={styles.title}>This could not be loaded</p>
      <p className={`${styles.text} muted`}>{messageFor(error)}</p>
      {reference ? <p className={`${styles.reference} faint ident`}>Reference {reference}</p> : null}
      {onRetry ? (
        <div className={styles.action}>
          <Button onClick={onRetry}>Try again</Button>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Shaped placeholders for whatever is loading, so a screen never looks empty and does not jump when the data lands:
 * `lines` for a small list or a note, `form` for a card of fields, `detail` for a document (the document and its side rail),
 * `page` for a whole screen (a header and a table). The label is read out to assistive technology.
 */
export function LoadingBlock({ label = "Loading", shape = "lines" }: { label?: string; shape?: "lines" | "form" | "detail" | "page" }) {
  return (
    <div className={styles.loading} role="status" aria-live="polite">
      {shape === "lines" ? <SkeletonLines lines={4} /> : null}
      {shape === "form" ? (
        <div className={styles.cardSkeleton}>
          <Skeleton width="30%" height="18px" />
          <div className={styles.fields}>
            {Array.from({ length: 6 }, (_, index) => (
              <div key={index} className={styles.field}>
                <Skeleton width="34%" height="10px" />
                <Skeleton width="100%" height="44px" block />
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {shape === "detail" ? (
        <div className={styles.detail}>
          <div className={styles.cardSkeleton}>
            <Skeleton width="42%" height="22px" />
            <SkeletonLines lines={3} />
            <Skeleton width="100%" height="120px" block />
            <SkeletonLines lines={2} />
          </div>
          <div className={styles.cardSkeleton}>
            <Skeleton width="50%" height="18px" />
            <Skeleton width="38%" height="26px" />
            <SkeletonLines lines={4} />
          </div>
        </div>
      ) : null}
      {shape === "page" ? (
        <div className={styles.pageSkeleton}>
          <Skeleton width="220px" height="30px" />
          <Skeleton width="360px" height="12px" />
          <div className={styles.cardSkeleton}>
            <Skeleton width="100%" height="44px" block />
            <table className={styles.fakeTable}>
              <SkeletonRows rows={7} columns={5} />
            </table>
          </div>
        </div>
      ) : null}
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

/** One shimmering bar: a line of text, a figure, a heading. Width and height are CSS lengths. */
export function Skeleton({ width = "100%", height, block }: { width?: string; height?: string; block?: boolean }) {
  return <span className={`${styles.skeleton} ${block ? styles.block : ""}`} style={{ width, height }} aria-hidden />;
}

/** A few lines of placeholder text, the last one shorter. */
export function SkeletonLines({ lines = 3 }: { lines?: number }) {
  return (
    <div className={styles.lines} aria-hidden>
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} width={index === lines - 1 ? "60%" : "100%"} />
      ))}
    </div>
  );
}

/** A card-shaped placeholder: a title bar, a big figure and a line, the shape of a dashboard card. */
export function SkeletonCard({ height }: { height?: string }) {
  return (
    <div className={styles.cardSkeleton} style={{ minHeight: height }} role="status" aria-live="polite">
      <Skeleton width="38%" />
      <Skeleton width="55%" height="28px" />
      <Skeleton width="80%" />
      <span className="sr-only">Loading</span>
    </div>
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
