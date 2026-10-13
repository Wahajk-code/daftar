"use client";

import {
  IconBell,
  IconHelpCircle,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconMenu2,
  IconMoon,
  IconNotebook,
  IconPlus,
  IconReceipt2,
  IconShoppingBag,
  IconSun,
  IconUserPlus,
} from "@tabler/icons-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import type { Me } from "@/api/types";
import { Dropdown } from "@/components/ui/Dropdown";
import { DateText, Money } from "@/components/ui/Format";
import { Skeleton } from "@/components/ui/States";
import { Stamp, Tag } from "@/components/ui/Stamp";
import { href as documentHref, KIND_LABEL, type Kind } from "@/lib/documents";
import { applyTheme } from "@/lib/preferences";
import { useWorkQueues } from "@/lib/queues";
import { notificationId, useSeen } from "@/lib/seen";
import { useCreate, type CreateKind } from "./CreateModal";
import { ProfileMenu } from "./ProfileMenu";
import styles from "./Header.module.css";

const KIND_TONE = { expenses: "teal", purchases: "info", vouchers: "violet" } as const;
const KIND_VERB: Record<Kind, string> = { expenses: "Written", purchases: "Entered", vouchers: "Prepared" };

const CREATE_ITEMS: Array<{ kind: CreateKind; label: string; hint: string; icon: typeof IconPlus }> = [
  { kind: "expense", label: "Expense", hint: "Money spent, with its receipt", icon: IconReceipt2 },
  { kind: "purchase", label: "Purchase", hint: "A vendor's invoice with lines and tax", icon: IconShoppingBag },
  { kind: "voucher", label: "Voucher", hint: "Debits and credits, posted to the books", icon: IconNotebook },
  { kind: "invite", label: "User invite", hint: "Invite someone by email and set their role", icon: IconUserPlus },
];

/** The "New" button: each kind of document opens in a modal over the current screen. */
function NewMenu() {
  const create = useCreate();
  const items = CREATE_ITEMS.filter((item) => create.allowed.includes(item.kind));
  if (items.length === 0) return null;
  return (
    <Dropdown
      label="Create something new"
      triggerClassName={styles.newButton}
      dataTour="new"
      width="300px"
      trigger={
        <>
          <IconPlus size={20} stroke={2} aria-hidden />
          <span>New</span>
        </>
      }
    >
      {(close) => (
        <ul className={styles.menu}>
          {items.map((item) => (
            <li key={item.kind}>
              <button
                type="button"
                onClick={() => {
                  close();
                  create.open(item.kind);
                }}
              >
                <span className={styles.menuIcon}>
                  <item.icon size={20} stroke={1.5} aria-hidden />
                </span>
                <span className={styles.menuText}>
                  <span className={styles.menuTitle}>{item.label}</span>
                  <span className={styles.menuHint}>{item.hint}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Dropdown>
  );
}

/** The bell: what is waiting for this person, from the same lists the home screen shows. */
function Bell({ me }: { me: Me }) {
  const pathname = usePathname();
  const { seen, mark } = useSeen(me.id);
  // A notification is a document waiting for this person that they have not opened yet. Opening it (from the bell or by any
  // other way) retires it; the document stays in the lists on the home screen until it is dealt with.
  const waiting = useWorkQueues(me).filter((queue) => queue.attention);
  const queues = waiting.map((queue) => ({ ...queue, items: queue.items?.filter((item) => !seen.has(notificationId(item.kind, item.id, item.status))) }));
  const loading = queues.some((queue) => queue.loading);
  const count = queues.reduce((total, queue) => total + (queue.items?.length ?? 0), 0);
  const opened = waiting
    .flatMap((queue) => queue.items ?? [])
    .find((item) => documentHref(item.kind, item.id) === pathname);
  const openedId = opened ? notificationId(opened.kind, opened.id, opened.status) : null;
  useEffect(() => {
    if (openedId) mark([openedId]);
  }, [openedId, mark]);

  return (
    <Dropdown
      label={count > 0 ? `Notifications, ${count} waiting` : "Notifications"}
      triggerClassName={styles.iconButton}
      dataTour="bell"
      width="420px"
      trigger={
        <>
          <IconBell size={22} stroke={1.5} aria-hidden />
          {count > 0 ? <span className={styles.badge}>{count > 99 ? "99+" : count}</span> : null}
        </>
      }
    >
      {(close) => (
        <div className={styles.bell}>
          <p className={styles.bellTitle}>Waiting for you</p>
          {loading && count === 0 ? (
            <div className={styles.bellSkeleton}>
              <Skeleton width="70%" />
              <Skeleton width="90%" />
              <Skeleton width="55%" />
            </div>
          ) : count === 0 ? (
            <p className={`${styles.bellEmpty} muted`}>Nothing needs you right now.</p>
          ) : (
            queues
              .filter((queue) => (queue.items?.length ?? 0) > 0)
              .map((queue) => (
                <section key={queue.key} aria-label={queue.title}>
                  <h3 className={styles.bellGroup}>
                    <span>{queue.title}</span>
                    <span className={styles.bellCount}>{queue.items?.length}</span>
                  </h3>
                  <ul className={styles.bellList}>
                    {queue.items?.slice(0, 4).map((item) => (
                      <li key={item.key}>
                        <Link
                          href={documentHref(item.kind, item.id)}
                          onClick={() => {
                            mark([notificationId(item.kind, item.id, item.status)]);
                            close();
                          }}
                          className={styles.bellItem}
                        >
                          <span className={styles.bellTop}>
                            <span className={`${styles.bellWhat} clip user-text`} title={item.title}>
                              {item.title}
                            </span>
                            <span className={`${styles.bellAmount} num`}>
                              <Money value={item.amount} />
                            </span>
                          </span>
                          <span className={styles.bellMeta}>
                            <Tag tone={KIND_TONE[item.kind]}>{KIND_LABEL[item.kind].singular}</Tag>
                            <Stamp status={item.status} />
                          </span>
                          <span className={styles.bellFoot}>
                            <span className="clip" title={`${KIND_VERB[item.kind]} by ${item.by}`}>
                              {KIND_VERB[item.kind]} by {item.by}
                            </span>
                            <span aria-hidden>·</span>
                            <DateText value={item.date} />
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  {queue.viewAll ? (
                    <Link href={queue.viewAll.href} onClick={close} className={styles.bellMore}>
                      {queue.viewAll.label}
                    </Link>
                  ) : null}
                </section>
              ))
          )}
        </div>
      )}
    </Dropdown>
  );
}

/** Light or dark in one press. The icon shows the one you would switch to; "System" is still where it starts. */
function ThemeToggle() {
  function toggle() {
    const root = document.documentElement;
    const set = root.getAttribute("data-theme");
    const dark = set ? set === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(dark ? "light" : "dark");
  }
  return (
    <button type="button" className={`${styles.iconButton} ${styles.theme}`} onClick={toggle} aria-label="Switch between the light and dark theme" data-tour="theme">
      <IconMoon size={22} stroke={1.5} aria-hidden className={styles.moon} />
      <IconSun size={22} stroke={1.5} aria-hidden className={styles.sun} />
    </button>
  );
}

/** The top bar: fold the sidebar, make something new, see what is waiting, switch theme, get help, and the account. */
export function Header({
  me,
  collapsed,
  drawerOpen,
  onToggleCollapsed,
  onOpenDrawer,
}: {
  me: Me;
  collapsed: boolean;
  drawerOpen: boolean;
  onToggleCollapsed: () => void;
  onOpenDrawer: () => void;
}) {
  return (
    <header className={styles.topbar}>
      <button type="button" className={`${styles.iconButton} ${styles.menuButton}`} onClick={onOpenDrawer} aria-label="Open the menu" aria-expanded={drawerOpen} aria-controls="sidebar">
        <IconMenu2 size={24} stroke={1.5} aria-hidden />
      </button>
      <button type="button" className={`${styles.iconButton} ${styles.railButton}`} onClick={onToggleCollapsed} aria-label={collapsed ? "Expand the sidebar" : "Collapse the sidebar"} aria-pressed={collapsed}>
        {collapsed ? <IconLayoutSidebarLeftExpand size={22} stroke={1.5} aria-hidden /> : <IconLayoutSidebarLeftCollapse size={22} stroke={1.5} aria-hidden />}
      </button>
      <span className={styles.spacer} />
      <NewMenu />
      <Bell me={me} />
      <ThemeToggle />
      <Link href="/help" className={styles.iconButton} aria-label="Help center" data-tour="help">
        <IconHelpCircle size={22} stroke={1.5} aria-hidden />
      </Link>
      <ProfileMenu me={me} />
    </header>
  );
}
