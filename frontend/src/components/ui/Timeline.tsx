"use client";

import type { HistoryItem } from "@/api/types";
import { Instant } from "./Format";
import { Stamp } from "./Stamp";
import styles from "./Timeline.module.css";

const ACTION_TEXT: Record<string, string> = {
  created: "created this",
  submitted: "sent it for approval",
  approved: "approved it",
  rejected: "rejected it",
  reopened: "reopened it for editing",
  posted: "posted it",
  voided: "voided it",
  reversed: "created it as the reversal of a voided voucher",
};

/**
 * The approval history, one component for every kind of document: who did what, when, with the comment they left. Newest
 * at the top.
 */
export function Timeline({ events }: { events: HistoryItem[] }) {
  const ordered = [...events].sort((a, b) => b.id - a.id);
  if (ordered.length === 0) return <p className="muted">Nothing has happened to this yet.</p>;
  return (
    <ol className={styles.list}>
      {ordered.map((event) => (
        <li key={event.id} className={styles.item}>
          <span className={styles.dot} aria-hidden />
          <div className={styles.content}>
            <p>
              <strong>{event.actor_name}</strong> {ACTION_TEXT[event.action] ?? event.action}
            </p>
            <p className={`${styles.when} faint`}>
              <Instant value={event.created_at} /> <Stamp status={event.to_status} />
            </p>
            {event.comment ? <p className={`${styles.comment} user-text`}>{event.comment}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
