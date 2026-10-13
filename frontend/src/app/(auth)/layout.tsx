import { LedgerArt } from "@/components/auth/LedgerArt";
import { Logo } from "@/components/shell/Logo";
import styles from "./auth.module.css";

/**
 * The four public screens share one layout: an illustrated half and the form, equal width from the tablet breakpoint up,
 * each a soft rounded card on the grey page. Below it the illustration goes and the panel shrinks to a compact header.
 */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className={styles.split}>
      <aside className={styles.brand} aria-label="About Daftar">
        <div className={styles.brandTop}>
          <Logo />
        </div>
        <div className={styles.art}>
          <LedgerArt />
        </div>
        <div className={styles.copy}>
          <p className={styles.line}>Every entry balanced, numbered and traceable.</p>
          <p className={styles.sub}>Expenses, purchases and vouchers, from the receipt to the ledger.</p>
        </div>
      </aside>
      <main className={styles.formSide} id="main">
        <div className={styles.formWrap}>{children}</div>
      </main>
    </div>
  );
}
