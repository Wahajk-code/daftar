import type { ReactNode } from "react";
import styles from "./template.module.css";

/** A template is drawn again on every navigation, so each screen eases in instead of cutting. */
export default function Template({ children }: { children: ReactNode }) {
  return <div className={styles.page}>{children}</div>;
}
