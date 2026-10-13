import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "quiet" | "danger";

interface Shared {
  variant?: Variant;
  icon?: ReactNode;
  small?: boolean;
}

function classes({ variant = "secondary", small }: Shared, extra?: string) {
  return [styles.button, styles[variant], small ? styles.small : "", extra ?? ""].filter(Boolean).join(" ");
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className={styles.spinner} role={label ? "status" : undefined} aria-label={label} aria-hidden={label ? undefined : true} />
  );
}

/**
 * A button. `pending` disables it, shows a spinner and tells assistive technology it is busy: every action that changes
 * something uses it, so a double click can never send twice.
 */
export function Button({
  variant,
  icon,
  small,
  pending = false,
  children,
  className,
  disabled,
  type = "button",
  ...rest
}: Shared & ButtonHTMLAttributes<HTMLButtonElement> & { pending?: boolean }) {
  return (
    <button
      {...rest}
      type={type}
      className={classes({ variant, small }, className)}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
    >
      {pending ? <Spinner /> : icon}
      {children ? <span>{children}</span> : null}
    </button>
  );
}

/** A link that looks like a button, for moving to another screen. */
export function ButtonLink({
  variant,
  icon,
  small,
  children,
  className,
  href,
  ...rest
}: Shared & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { href: string }) {
  return (
    <Link {...rest} href={href} className={classes({ variant, small }, className)}>
      {icon}
      <span>{children}</span>
    </Link>
  );
}
