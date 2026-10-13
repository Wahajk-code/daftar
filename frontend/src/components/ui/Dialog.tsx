"use client";

import { IconX } from "@tabler/icons-react";
import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
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
  size = wide ? "lg" : "sm",
  description,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Same as size "lg". */
  wide?: boolean;
  /** sm (a question), lg (a short form), xl (a document form). On a phone every size fills the screen. */
  size?: "sm" | "lg" | "xl";
  description?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  // The sheet stays drawn while it leaves, so closing is an animation rather than a cut.
  const [shown, setShown] = useState(open);
  if (open && !shown) setShown(true);

  const finishClosing = useCallback(() => {
    const dialog = ref.current;
    if (!dialog || !dialog.hasAttribute("data-closing")) return;
    dialog.removeAttribute("data-closing");
    dialog.close();
    setShown(false);
  }, []);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open) {
      dialog.removeAttribute("data-closing");
      if (!dialog.open) dialog.showModal();
      return;
    }
    if (!dialog.open) return;
    dialog.setAttribute("data-closing", "");
    // The animation end closes it; this timer is the backstop (reduced motion, or an interrupted animation).
    const timer = window.setTimeout(finishClosing, 260);
    return () => window.clearTimeout(timer);
  }, [open, finishClosing]);

  return (
    <dialog
      ref={ref}
      className={`${styles.dialog} ${styles[size]}`}
      aria-labelledby={titleId}
      onCancel={(event) => {
        // Escape asks to close; the parent decides, and the sheet then animates out.
        event.preventDefault();
        onClose();
      }}
      onAnimationEnd={(event) => event.target === ref.current && finishClosing()}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      {open || shown ? (
        <div className={styles.frame}>
          <div className={styles.head}>
            <div className={styles.headText}>
              <h2 id={titleId}>{title}</h2>
              {description ? <p className="muted">{description}</p> : null}
            </div>
            <button type="button" className={styles.close} onClick={onClose} aria-label="Close">
              <IconX size={20} stroke={1.75} aria-hidden />
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
