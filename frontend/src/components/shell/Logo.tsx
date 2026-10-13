import styles from "./Logo.module.css";

/**
 * The mark: an open ledger with its ruled lines. Each stroke draws itself in one after the other when the page loads, and
 * the name fades in beside it. With reduced motion the finished mark is shown at once (the stylesheet shortens every
 * animation), and a shared `pathLength` of 1 lets one rule drive every stroke.
 */
export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg className={styles.mark} width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <rect className={styles.tile} x="1" y="1" width="30" height="30" rx="10" />
      <path className={`${styles.stroke} ${styles.book}`} pathLength="1" d="M8 10.5c2.6-.9 5.4-.6 8 1 2.6-1.6 5.4-1.9 8-1v12c-2.6-.9-5.4-.6-8 1-2.6-1.6-5.4-1.9-8-1z" />
      <path className={`${styles.stroke} ${styles.spine}`} pathLength="1" d="M16 11.5v12" />
      <path className={`${styles.stroke} ${styles.ruleA}`} pathLength="1" d="M10.5 14.2c1.5-.3 3-.1 4.2.6" />
      <path className={`${styles.stroke} ${styles.ruleB}`} pathLength="1" d="M10.5 17.6c1.5-.3 3-.1 4.2.6" />
      <path className={`${styles.stroke} ${styles.ruleC}`} pathLength="1" d="M17.3 14.8c1.2-.7 2.7-.9 4.2-.6" />
    </svg>
  );
}

export function Logo({ showName = true }: { showName?: boolean }) {
  return (
    <span className={styles.logo}>
      <LogoMark />
      {showName ? (
        <span className={styles.name}>
          Daftar <span lang="ur" className={styles.urdu}>دفتر</span>
        </span>
      ) : null}
    </span>
  );
}
