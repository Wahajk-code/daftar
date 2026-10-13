import { IconArrowUpRight } from "@tabler/icons-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Skeleton } from "./States";
import styles from "./StatCard.module.css";

/**
 * A figure on a card: what it is, the number, one line of context. The whole card is a link when it leads somewhere (the
 * arrow says so). `dark` is the one card a screen leads with; `hero` sets its figure at display size. While the figure
 * loads, a shimmer holds its place so the card never looks empty.
 */
export function StatCard({
  label,
  value,
  hint,
  href,
  dark,
  hero,
  loading,
  icon,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  href?: string;
  dark?: boolean;
  hero?: boolean;
  loading?: boolean;
  icon?: ReactNode;
}) {
  const body = (
    <>
      <span className={styles.top}>
        <span className={styles.label}>{label}</span>
        {href ? (
          <span className={styles.go} aria-hidden>
            <IconArrowUpRight size={18} stroke={1.75} />
          </span>
        ) : icon ? (
          <span className={styles.go} aria-hidden>
            {icon}
          </span>
        ) : null}
      </span>
      <span className={`${styles.value} ${hero ? styles.hero : ""}`}>{loading ? <Skeleton width="60%" height={hero ? "40px" : "28px"} /> : value}</span>
      <span className={styles.hint}>{loading ? <Skeleton width="80%" /> : hint}</span>
    </>
  );
  const className = `${styles.card} ${dark ? styles.dark : ""} ${href ? styles.link : ""}`;
  return href ? (
    <Link href={href} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}
