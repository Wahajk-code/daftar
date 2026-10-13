"use client";

import { IconChevronLeft, IconChevronRight, IconExternalLink } from "@tabler/icons-react";
import { useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import styles from "./ReceiptLightbox.module.css";

export interface ReceiptItem {
  /** Where the picture is: a path on the API or a local object URL. */
  src: string;
  name: string;
  /** A line under the name, such as the size. */
  meta?: string;
  /** A page that shows the original, when there is one. */
  href?: string;
}

/**
 * A large view of a receipt over the page, with the others one press away (the arrow keys work too). The picture is shown as
 * it is: the theme never inverts or tints a receipt.
 */
export function ReceiptLightbox({ items, index, onIndex, onClose }: { items: ReceiptItem[]; index: number | null; onIndex: (next: number) => void; onClose: () => void }) {
  const open = index !== null && items[index] !== undefined;
  const current = open ? items[index] : undefined;

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") onIndex(Math.min(items.length - 1, (index ?? 0) + 1));
      if (event.key === "ArrowLeft") onIndex(Math.max(0, (index ?? 0) - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, index, items.length, onIndex]);

  return (
    <Dialog open={open} onClose={onClose} size="lg" title={current?.name ?? "Receipt"} description={current?.meta}>
      {current ? (
        <div className={styles.view}>
          <div className={styles.stage}>
            {/* The receipt as it is: never inverted or tinted by the theme. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={current.src} alt={`Receipt ${current.name}`} className={styles.image} />
          </div>
          <div className={styles.bar}>
            <Button small icon={<IconChevronLeft size={18} stroke={1.75} aria-hidden />} disabled={(index ?? 0) === 0} onClick={() => onIndex((index ?? 0) - 1)} aria-label="Previous receipt" />
            <span className={styles.count}>
              {(index ?? 0) + 1} of {items.length}
            </span>
            <Button small icon={<IconChevronRight size={18} stroke={1.75} aria-hidden />} disabled={(index ?? 0) >= items.length - 1} onClick={() => onIndex((index ?? 0) + 1)} aria-label="Next receipt" />
            <span className={styles.spacer} />
            {current.href ? (
              <a href={current.href} target="_blank" rel="noopener noreferrer" className={styles.open}>
                <IconExternalLink size={18} stroke={1.75} aria-hidden /> Open the original
              </a>
            ) : null}
          </div>
        </div>
      ) : null}
    </Dialog>
  );
}
