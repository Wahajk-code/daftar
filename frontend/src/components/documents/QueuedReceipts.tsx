"use client";

import { IconCamera, IconFileUpload, IconX } from "@tabler/icons-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { prepareReceipt } from "@/lib/images";
import { ReceiptLightbox } from "./ReceiptLightbox";
import styles from "./QueuedReceipts.module.css";

function sizeText(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/**
 * Receipts chosen before the document is saved: each shows as a picture straight away (made from the file on this device),
 * opens large on a press, and can be taken out. They are uploaded when the document is saved.
 */
export function QueuedReceipts({ files, onChange, empty, chooseLabel }: { files: File[]; onChange: (next: File[]) => void; empty: string; chooseLabel: string }) {
  const input = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const [viewing, setViewing] = useState<number | null>(null);
  const urls = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);
  // Each picture's temporary address is released when the list changes or the form closes.
  useEffect(() => () => urls.forEach((url) => URL.revokeObjectURL(url)), [urls]);

  return (
    <div className={styles.queue}>
      {files.length === 0 ? <p className="muted">{empty}</p> : null}
      <ul className={styles.gallery}>
        {files.map((file, index) => (
          <li key={`${file.name}-${index}`} className={styles.thumb}>
            <button type="button" className={styles.picture} onClick={() => setViewing(index)} aria-label={`Preview ${file.name}`}>
              {/* A local picture: the receipt as it is. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={urls[index]} alt="" />
            </button>
            <div className={styles.meta}>
              <span className={`${styles.name} clip`} title={file.name}>
                {file.name}
              </span>
              <span className="faint">{sizeText(file.size)}</span>
            </div>
            <Button small variant="quiet" className={styles.remove} icon={<IconX size={18} stroke={1.75} aria-hidden />} onClick={() => onChange(files.filter((_, at) => at !== index))} aria-label={`Remove ${file.name}`} />
          </li>
        ))}
      </ul>
      <input
        ref={input}
        type="file"
        hidden
        multiple
        accept="image/jpeg,image/png,image/webp"
        onChange={async (event) => {
          const chosen = await Promise.all(Array.from(event.target.files ?? []).map(prepareReceipt));
          event.target.value = "";
          onChange([...files, ...chosen]);
        }}
      />
      <input
        ref={camera}
        type="file"
        hidden
        accept="image/*"
        capture="environment"
        tabIndex={-1}
        onChange={async (event) => {
          const taken = await Promise.all(Array.from(event.target.files ?? []).map(prepareReceipt));
          event.target.value = "";
          onChange([...files, ...taken]);
        }}
      />
      <div className={styles.buttons}>
        <Button className="touch-only" icon={<IconCamera size={20} stroke={1.75} aria-hidden />} onClick={() => camera.current?.click()}>
          Take a photo
        </Button>
        <Button icon={<IconFileUpload size={20} stroke={1.75} aria-hidden />} onClick={() => input.current?.click()}>
          {chooseLabel}
        </Button>
      </div>
      <ReceiptLightbox items={files.map((file, index) => ({ src: urls[index], name: file.name, meta: sizeText(file.size) }))} index={viewing} onIndex={setViewing} onClose={() => setViewing(null)} />
    </div>
  );
}
