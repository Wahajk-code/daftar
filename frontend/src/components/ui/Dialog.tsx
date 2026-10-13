"use client";

import { IconX } from "@tabler/icons-react";
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { messageFor } from "@/api/errors";
import { Button } from "./Button";
import { TextAreaField } from "./Field";
import styles from "./Dialog.module.css";

/**
 * A modal built on the browser's own <dialog>: it traps focus, closes on Escape, and gives focus back to whatever opened
 * it. A click on the dimmed area closes it too.
 */
export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`${styles.dialog} ${wide ? styles.wide : ""}`}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      {open ? (
        <div className={styles.frame}>
          <div className={styles.head}>
            <h2 id={titleId}>{title}</h2>
            <button type="button" className={styles.close} onClick={onClose} aria-label="Close">
              <IconX size={18} stroke={1.75} aria-hidden />
            </button>
          </div>
          <div className={styles.body}>{children}</div>
          {footer ? <div className={styles.footer}>{footer}</div> : null}
        </div>
      ) : null}
    </dialog>
  );
}

/**
 * Asks before doing something that cannot be taken back. Optionally collects the reason or comment the action needs. It
 * stays open and shows the failure if the action is refused, and closes only when the action succeeds.
 */
export function ConfirmDialog({
  open,
  onClose,
  title,
  children,
  confirmLabel,
  danger,
  reasonLabel,
  reasonRequired = true,
  reasonHint,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  reasonLabel?: string;
  reasonRequired?: boolean;
  reasonHint?: string;
  onConfirm: (reason: string) => Promise<unknown>;
}) {
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [problem, setProblem] = useState<string | undefined>();

  const reasonMissing = reasonLabel !== undefined && reasonRequired && reason.trim() === "";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reasonMissing) {
      setProblem(`${reasonLabel} is required.`);
      return;
    }
    setPending(true);
    setProblem(undefined);
    try {
      await onConfirm(reason.trim());
      setReason("");
      onClose();
    } catch (error) {
      setProblem(messageFor(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onClose={pending ? () => undefined : onClose} title={title}>
      <form onSubmit={submit} className={styles.form} noValidate>
        {children ? <div className={styles.text}>{children}</div> : null}
        {reasonLabel ? (
          <TextAreaField
            label={reasonLabel}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            hint={reasonHint}
            required={reasonRequired}
            error={problem && reasonMissing ? problem : undefined}
            autoFocus
          />
        ) : null}
        {problem && !reasonMissing ? (
          <p className={styles.problem} role="alert">
            {problem}
          </p>
        ) : null}
        <div className={styles.actions}>
          <Button onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button type="submit" variant={danger ? "danger" : "primary"} pending={pending}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
