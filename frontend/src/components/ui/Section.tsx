import type { ReactNode } from "react";
import styles from "./Section.module.css";

/**
 * A named part of a screen: a heading with a line of explanation, a hairline above it to set it apart from the section before,
 * and room below. Cards inside a section sit in a grid that never makes a card narrower than it can be read at.
 */
export function Section({
  title,
  description,
  count,
  urgent,
  actions,
  children,
  id,
}: {
  title: string;
  description?: string;
  /** A number beside the title: how many things are in the section. Red when `urgent`. */
  count?: number;
  urgent?: boolean;
  actions?: ReactNode;
  children: ReactNode;
  id: string;
}) {
  return (
    <section className={styles.section} aria-labelledby={`${id}-title`}>
      <header className={styles.head}>
        <div className={styles.titles}>
          <h2 id={`${id}-title`} className={styles.title}>
            {title}
            {count !== undefined ? <span className={`${styles.count} ${urgent && count > 0 ? styles.urgent : ""}`}>{count}</span> : null}
          </h2>
          {description ? <p className={styles.description}>{description}</p> : null}
        </div>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </header>
      {children}
    </section>
  );
}

/** The grid cards sit in. `wide` is for cards that need more room (tables): none is ever narrower than the size given. */
export function CardGrid({ children, min = 360, className }: { children: ReactNode; min?: number; className?: string }) {
  return (
    <div className={`${styles.grid} ${className ?? ""}`} style={{ "--min": `${min}px` } as React.CSSProperties}>
      {children}
    </div>
  );
}
