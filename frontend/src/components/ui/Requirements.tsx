import { IconListCheck } from "@tabler/icons-react";
import styles from "./Requirements.module.css";

/**
 * What a form still needs before its button works, kept in view beside the button. It follows the form live and goes when
 * nothing is missing, so a disabled button always comes with its reason.
 */
export function Requirements({ items, lead = "Still needed" }: { items: string[]; lead?: string }) {
  if (items.length === 0) return null;
  return (
    <p className={styles.requirements} role="status">
      <IconListCheck size={20} stroke={1.75} aria-hidden />
      <span>
        <strong>{lead}:</strong> {items.join(", ")}
      </span>
    </p>
  );
}
