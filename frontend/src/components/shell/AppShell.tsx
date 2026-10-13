"use client";

import { IconLogout, IconX } from "@tabler/icons-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import type { Me } from "@/api/types";
import { navigate } from "@/lib/navigate";
import { applySidebar } from "@/lib/preferences";
import { CreateProvider } from "./CreateModal";
import { Header } from "./Header";
import { Logo } from "./Logo";
import { MeProvider } from "./MeContext";
import { Tour } from "./Tour";
import { isCurrent, navFor } from "./nav";
import styles from "./AppShell.module.css";

/**
 * The frame around every signed-in screen: a floating sidebar that folds to an icon rail, a top bar that carries the
 * person's tools (new, notifications, theme, help, account), and the content. On a phone the sidebar becomes a drawer. The
 * folded state is remembered in a cookie, so the page is drawn the right way on first paint.
 */
export function AppShell({ me, initialCollapsed, children }: { me: Me; initialCollapsed: boolean; children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const groups = navFor(me.role);

  // Escape closes the drawer; choosing a place in it closes it too (see the links below).
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  async function signOut() {
    setLeaving(true);
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    } finally {
      navigate("/login");
    }
  }

  function toggleCollapsed() {
    setCollapsed((current) => {
      applySidebar(!current);
      return !current;
    });
  }

  return (
    <MeProvider me={me}>
      <CreateProvider role={me.role}>
        <div className={styles.shell}>
          <a href="#main" className={styles.skip}>
            Skip to the content
          </a>

          <aside id="sidebar" className={`${styles.sidebar} ${drawerOpen ? styles.open : ""}`} aria-label="Main">
            <div className={styles.brand}>
              <Link href="/" className={styles.brandLink} aria-label="Daftar home">
                <Logo showName={!collapsed || drawerOpen} />
              </Link>
              <button type="button" className={styles.drawerClose} onClick={() => setDrawerOpen(false)} aria-label="Close the menu">
                <IconX size={22} stroke={1.75} aria-hidden />
              </button>
            </div>
            <nav className={styles.nav}>
              {groups.map((group, index) => (
                <div key={group.heading ?? index} className={styles.group}>
                  {group.heading ? <p className={styles.heading}>{group.heading}</p> : null}
                  <ul>
                    {group.items.map((item) => {
                      const current = isCurrent(pathname, item);
                      return (
                        <li key={item.href}>
                          <Link
                            href={item.href}
                            className={`${styles.item} ${current ? styles.current : ""}`}
                            aria-current={current ? "page" : undefined}
                            aria-label={collapsed ? item.label : undefined}
                            data-tip={item.label}
                            data-tour={`nav-${item.href === "/" ? "home" : item.href.slice(1)}`}
                            onClick={() => setDrawerOpen(false)}
                          >
                            <item.icon size={22} stroke={1.5} aria-hidden className={styles.itemIcon} />
                            <span className={styles.itemLabel}>{item.label}</span>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </nav>
            <button
              type="button"
              className={styles.signOut}
              onClick={signOut}
              disabled={leaving}
              aria-busy={leaving || undefined}
              aria-label="Log out"
              data-tip="Log out"
            >
              <IconLogout size={22} stroke={1.5} aria-hidden />
              <span className={styles.itemLabel}>{leaving ? "Logging out" : "Log out"}</span>
            </button>
          </aside>

          {drawerOpen ? <div className={styles.scrim} onClick={() => setDrawerOpen(false)} aria-hidden /> : null}

          <div className={styles.main}>
            <Header me={me} collapsed={collapsed} drawerOpen={drawerOpen} onToggleCollapsed={toggleCollapsed} onOpenDrawer={() => setDrawerOpen(true)} />
            <main id="main" tabIndex={-1} className={styles.content}>
              {children}
            </main>
          </div>
          <Tour />
        </div>
      </CreateProvider>
    </MeProvider>
  );
}
