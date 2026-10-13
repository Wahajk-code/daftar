import Link from "next/link";
import { IconChevronLeft } from "@tabler/icons-react";
import type { ReactNode } from "react";
import { PrintButton, PrintStamp } from "./PrintButton";
import styles from "./Layout.module.css";

/** The title of a screen, what it is for, and the things that can be done from it. */
export function PageHeader({
  title,
  description,
  actions,
  back,
  meta,
  print = true,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: { href: string; label: string };
  meta?: ReactNode;
  /** Draws the Print button beside the actions. Off for screens that are not worth printing. */
  print?: boolean;
}) {
  return (
    <header className={styles.header}>
      <PrintStamp />
      {back ? (
        <Link href={back.href} className={styles.back} data-noprint>
          <IconChevronLeft size={18} stroke={1.75} aria-hidden />
          {back.label}
        </Link>
      ) : null}
      <div className={styles.headerRow}>
        <div className={styles.headerText}>
          <h1>{title}</h1>
          {meta ? <div className={styles.meta}>{meta}</div> : null}
          {description ? <p className={`${styles.description} muted`}>{description}</p> : null}
        </div>
        {actions || print ? (
          <div className={styles.actions} data-noprint>
            {actions}
            {print ? <PrintButton /> : null}
          </div>
        ) : null}
      </div>
    </header>
  );
}

/** A white card with a soft shadow: the unit the screens are built from. */
export function Panel({
  title,
  actions,
  children,
  flush,
  className,
  id,
  noPrint,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  /** No padding: for a table that runs edge to edge. */
  flush?: boolean;
  className?: string;
  id?: string;
  /** Left off the paper copy (a history, a set of receipt pictures). */
  noPrint?: boolean;
}) {
  return (
    <section
      className={`${styles.panel} ${className ?? ""}`}
      aria-labelledby={title && id ? `${id}-title` : undefined}
      id={id}
      data-print-card
      data-noprint={noPrint ? "" : undefined}
    >
      {title || actions ? (
        <div className={styles.panelHead}>
          {title ? <h2 id={id ? `${id}-title` : undefined}>{title}</h2> : <span />}
          {actions ? <div className={styles.panelActions}>{actions}</div> : null}
        </div>
      ) : null}
      <div className={flush ? styles.panelFlush : styles.panelBody}>{children}</div>
    </section>
  );
}

/** A label and its value, as they appear in a document's margin. */
export function Facts({ items }: { items: Array<{ label: string; value: ReactNode }> }) {
  return (
    <dl className={styles.facts}>
      {items.map((item) => (
        <div key={item.label} className={styles.fact}>
          <dt>{item.label}</dt>
          <dd>{item.value ?? <span className="faint">None</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Rows of fields laid out in a responsive grid. */
export function FormGrid({ children, columns = 2 }: { children: ReactNode; columns?: 1 | 2 | 3 }) {
  return <div className={`${styles.formGrid} ${styles[`cols${columns}`]}`}>{children}</div>;
}
