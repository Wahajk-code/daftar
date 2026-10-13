"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import styles from "./Dropdown.module.css";

/**
 * A button that opens a small panel under it: the "New" menu, the bell, the filters. It closes on Escape (returning focus to
 * the button), on a press outside, and when the panel asks to (`close`). The panel is a labelled region, not a menu role, so
 * it can hold links, lists and form controls.
 */
export function Dropdown({
  label,
  trigger,
  triggerClassName,
  children,
  align = "end",
  width,
  dataTour,
}: {
  /** The accessible name of the button. */
  label: string;
  /** What the button shows. */
  trigger: ReactNode;
  triggerClassName?: string;
  children: (close: () => void) => ReactNode;
  align?: "start" | "end";
  /** A CSS width for the panel. */
  width?: string;
  dataTour?: string;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={root} className={styles.root}>
      <button
        ref={button}
        type="button"
        className={triggerClassName}
        aria-label={label}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        data-tour={dataTour}
        onClick={() => setOpen((current) => !current)}
      >
        {trigger}
      </button>
      {open ? (
        <div id={panelId} role="region" aria-label={label} data-noprint className={`${styles.panel} ${align === "end" ? styles.end : styles.start}`} style={width ? { width } : undefined}>
          {children(() => setOpen(false))}
        </div>
      ) : null}
    </div>
  );
}
