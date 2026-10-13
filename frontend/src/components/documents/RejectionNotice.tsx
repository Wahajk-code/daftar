"use client";

import { IconMessageExclamation } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { DocumentStatus, HistoryItem } from "@/api/types";
import { Instant } from "@/components/ui/Format";
import type { Kind } from "@/lib/documents";
import styles from "./RejectionNotice.module.css";

/**
 * Why a document was sent back, in full, at the top of the document itself: the reviewer's own words, who said it and when,
 * highlighted so the author cannot miss it. (The history keeps every comment too, but a rejection is the one a person has to
 * act on, so it is not left for them to dig out.) Shown only while the document is rejected.
 */
export function RejectionNotice({ kind, id, status, isAuthor }: { kind: Kind; id: number; status: DocumentStatus; isAuthor: boolean }) {
  const history = useQuery({
    queryKey: ["history", kind, id],
    queryFn: () => api<HistoryItem[]>(`/${kind}/${id}/history`),
    enabled: status === "rejected",
  });
  if (status !== "rejected") return null;
  const rejection = [...(history.data ?? [])].sort((a, b) => b.id - a.id).find((event) => event.action === "rejected");

  return (
    <section className={styles.notice} aria-labelledby={`rejection-${id}`}>
      <div className={styles.head}>
        <IconMessageExclamation size={28} stroke={1.5} aria-hidden className={styles.icon} />
        <div>
          <h2 id={`rejection-${id}`} className={styles.title}>
            Sent back{rejection ? ` by ${rejection.actor_name}` : ""}
          </h2>
          {rejection ? (
            <p className={styles.when}>
              <Instant value={rejection.created_at} />
            </p>
          ) : null}
        </div>
      </div>
      {history.isPending ? (
        <p className={styles.comment}>Loading the comment from the reviewer.</p>
      ) : rejection?.comment ? (
        <blockquote className={`${styles.comment} user-text`}>{rejection.comment}</blockquote>
      ) : (
        <p className={styles.comment}>The reviewer did not leave a comment.</p>
      )}
      {isAuthor ? <p className={styles.next}>Change what is asked, then reopen it for editing and send it for approval again.</p> : null}
    </section>
  );
}
