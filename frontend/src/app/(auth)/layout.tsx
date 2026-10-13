import { IconNotebook } from "@tabler/icons-react";
import styles from "./auth.module.css";

/**
 * The four public screens share one layout: a brand panel and the form, equal width from the tablet breakpoint up. Below
 * it the panel shrinks to a compact header. The panel is made from the product's own tokens: ruled paper with a debit
 * and a credit column, and no figures, because there is nothing real to count before someone has signed in.
 */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className={styles.split}>
      <aside className={styles.brand} aria-label="About Daftar">
        <div className={styles.brandTop}>
          <IconNotebook size={28} stroke={1.5} aria-hidden />
          <span className={styles.wordmark}>Daftar</span>
          <span lang="ur" className={styles.urdu}>
            دفتر
          </span>
        </div>
        <div className={styles.sheet} aria-hidden>
          <div className={styles.sheetHead}>
            <span>Particulars</span>
            <span>Debit</span>
            <span>Credit</span>
          </div>
          {Array.from({ length: 9 }, (_, row) => (
            <div key={row} className={styles.sheetRow} />
          ))}
        </div>
        <p className={styles.line}>Expenses, purchases and vouchers, balanced, numbered and traceable.</p>
      </aside>
      <main className={styles.formSide} id="main">
        <div className={styles.formWrap}>{children}</div>
      </main>
    </div>
  );
}
