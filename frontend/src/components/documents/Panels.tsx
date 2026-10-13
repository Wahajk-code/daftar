"use client";

import { IconFileUpload, IconTrash } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";
import { api, upload } from "@/api/client";
import { messageFor } from "@/api/errors";
import { DOCUMENT_KEYS, useAction } from "@/api/queries";
import type { Attachment, DuplicateWarning, HistoryItem } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { DateText, Money } from "@/components/ui/Format";
import { Banner, ErrorState, LoadingBlock } from "@/components/ui/States";
import { prepareReceipt } from "@/lib/images";
import { ReceiptLightbox } from "./ReceiptLightbox";
import { Stamp } from "@/components/ui/Stamp";
import { Timeline } from "@/components/ui/Timeline";
import { href, type Kind } from "@/lib/documents";
import styles from "./Panels.module.css";

/** The approval history of any document. One component, three kinds. */
export function HistoryPanel({ kind, id }: { kind: Kind; id: number }) {
  const history = useQuery({ queryKey: ["history", kind, id], queryFn: () => api<HistoryItem[]>(`/${kind}/${id}/history`) });
  if (history.isPending) return <LoadingBlock label="Loading the history" />;
  if (history.error) return <ErrorState error={history.error} onRetry={() => history.refetch()} />;
  return <Timeline events={history.data} />;
}

const DUPLICATE_TITLE: Record<DuplicateWarning["kind"], string> = {
  same_invoice: "Same invoice number",
  similar: "Looks like another document",
  same_receipt: "Same receipt",
};

/** Documents that resemble this one. Advice only: nothing is blocked. */
export function DuplicatePanel({ kind, id }: { kind: "expenses" | "purchases"; id: number }) {
  const found = useQuery({ queryKey: ["duplicates", kind, id], queryFn: () => api<DuplicateWarning[]>(`/${kind}/${id}/duplicates`) });
  if (!found.data || found.data.length === 0) return null;
  return (
    <Banner tone="caution" title="This may be a duplicate" noPrint>
      <ul className={styles.duplicates}>
        {found.data.map((warning) => {
          const target = warning.document_type === "expense" ? "expenses" : warning.document_type === "purchase" ? "purchases" : "vouchers";
          return (
            <li key={`${warning.kind}-${warning.document_type}-${warning.document_id}`}>
              <strong>{DUPLICATE_TITLE[warning.kind]}.</strong> {warning.reason}{" "}
              <Link href={href(target, warning.document_id)}>
                Open {warning.document_type} {warning.document_id}
              </Link>{" "}
              (<DateText value={warning.document_date} />, <Money value={warning.amount} />, <Stamp status={warning.status} />)
            </li>
          );
        })}
      </ul>
      <p className={styles.advice}>You can still save, send and approve it. This is only a warning.</p>
    </Banner>
  );
}

const ACCEPT = "image/*";

function sizeText(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(Math.round((bytes / (1024 * 1024)) * 10) / 10).toFixed(1)} MB`;
}

/**
 * Receipts on an expense or a purchase. Images are shown through the API (they are private), uploads show their progress,
 * and while the document is a draft the author can remove one.
 */
export function ReceiptPanel({ kind, id, editable }: { kind: "expenses" | "purchases"; id: number; editable: boolean }) {
  const files = useQuery({ queryKey: ["record", kind, id, "attachments"], queryFn: () => api<Attachment[]>(`/${kind}/${id}/attachments`) });
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [viewing, setViewing] = useState<number | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const send = useAction<File[], unknown>({
    mutationFn: async (chosen) => {
      setFailure(null);
      for (const original of chosen) {
        const file = await prepareReceipt(original);
        setProgress((current) => ({ ...current, [file.name]: 0 }));
        try {
          await upload(`/${kind}/${id}/attachments`, file, (fraction) => setProgress((current) => ({ ...current, [file.name]: fraction })));
        } catch (error) {
          setFailure(`${file.name}: ${messageFor(error)}`);
          throw error;
        } finally {
          setProgress((current) => {
            const next = { ...current };
            delete next[file.name];
            return next;
          });
        }
      }
    },
    success: (_, chosen) => (chosen.length === 1 ? "Receipt added" : "Receipts added"),
    invalidate: [["record", kind, id, "attachments"], ...DOCUMENT_KEYS.filter((key) => key[0] === "duplicates")],
  });

  const remove = useAction<number, unknown>({
    mutationFn: (attachmentId) => api(`/attachments/${attachmentId}/remove`, { method: "POST" }),
    success: "Receipt removed",
    invalidate: [["record", kind, id, "attachments"], ["duplicates"]],
  });

  if (files.isPending) return <LoadingBlock label="Loading the receipts" />;
  if (files.error) return <ErrorState error={files.error} onRetry={() => files.refetch()} />;

  const uploading = Object.keys(progress);
  const items = files.data.map((file) => ({
    src: `/api/attachments/${file.id}/content`,
    name: file.original_name,
    meta: sizeText(file.size_bytes),
    href: `/api/attachments/${file.id}/content`,
  }));
  return (
    <div className={styles.receipts}>
      <ReceiptLightbox items={items} index={viewing} onIndex={setViewing} onClose={() => setViewing(null)} />
      {files.data.length === 0 && uploading.length === 0 ? <p className="muted">No receipt is attached.</p> : null}
      <ul className={styles.gallery}>
        {files.data.map((file) => (
          <li key={file.id} className={styles.thumb}>
            <button type="button" className={styles.picture} onClick={() => setViewing(files.data.indexOf(file))} aria-label={`Preview ${file.original_name}`}>
              {/* The receipt as it is: never inverted or tinted by the theme. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/attachments/${file.id}/content`} alt={`Receipt ${file.original_name}`} loading="lazy" />
            </button>
            <div className={styles.thumbMeta}>
              <span className="ident">{file.original_name}</span>
              <span className="faint">{sizeText(file.size_bytes)}</span>
              {editable ? (
                <Button small variant="quiet" icon={<IconTrash size={16} stroke={1.75} aria-hidden />} pending={remove.isPending && remove.variables === file.id} onClick={() => remove.mutate(file.id)} aria-label={`Remove ${file.original_name}`}>
                  Remove
                </Button>
              ) : null}
            </div>
          </li>
        ))}
        {uploading.map((name) => (
          <li key={name} className={styles.thumb}>
            <div className={styles.uploading} role="progressbar" aria-label={`Uploading ${name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((progress[name] ?? 0) * 100)}>
              <span className={styles.progressFill} style={{ width: `${Math.round((progress[name] ?? 0) * 100)}%` }} />
            </div>
            <div className={styles.thumbMeta}>
              <span className="ident">{name}</span>
              <span className="faint">{Math.round((progress[name] ?? 0) * 100)}%</span>
            </div>
          </li>
        ))}
      </ul>
      {failure ? (
        <p className={styles.failure} role="alert">
          {failure}
        </p>
      ) : null}
      {editable ? (
        <div>
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={(event) => {
              const chosen = Array.from(event.target.files ?? []);
              event.target.value = "";
              if (chosen.length > 0) send.mutate(chosen);
            }}
          />
          <Button icon={<IconFileUpload size={18} stroke={1.75} aria-hidden />} pending={send.isPending} onClick={() => input.current?.click()}>
            Add a receipt
          </Button>
          <p className={`${styles.advice} faint`}>JPEG, PNG or WebP. Location data is removed from the photo.</p>
        </div>
      ) : null}
    </div>
  );
}
