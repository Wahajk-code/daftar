import type { DocumentStatus } from "@/api/types";
import styles from "./Stamp.module.css";

const LABELS: Record<DocumentStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  rejected: "Rejected",
  posted: "Posted",
  void: "Void",
};

/**
 * A status as a stamp: an outlined box in mono capitals, the way a clerk marks a voucher. The meaning is in the word, never
 * the colour alone.
 */
export function Stamp({ status, label }: { status: DocumentStatus; label?: string }) {
  return <span className={`${styles.stamp} ${styles[status]}`}>{label ?? LABELS[status]}</span>;
}

export function statusLabel(status: DocumentStatus): string {
  return LABELS[status];
}

/** Something that is not a document status but wants the same look: "Inactive", "Registered". */
export function Tag({ tone = "neutral", children }: { tone?: "neutral" | "positive" | "caution" | "negative"; children: string }) {
  return <span className={`${styles.stamp} ${styles[`tag-${tone}`]}`}>{children}</span>;
}
