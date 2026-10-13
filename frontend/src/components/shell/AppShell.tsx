"use client";

import {
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconMenu2,
  IconNotebook,
  IconX,
} from "@tabler/icons-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import type { Me } from "@/api/types";
import { applySidebar, type Density, type Theme } from "@/lib/preferences";
import { MeProvider } from "./MeContext";
import { Tour } from "./Tour";
import { ProfileMenu } from "./ProfileMenu";
import { isCurrent, navFor } from "./nav";
import styles from "./AppShell.module.css";

/**
 * The frame around every signed-in screen: a sidebar that folds to an icon rail, a top bar, and the content. On a phone the
 * sidebar becomes a drawer. The folded state is remembered in a cookie, so the page is drawn the right way on first paint.
 */
export function AppShell({
  me,
  initialCollapsed,
  initialTheme,
  initialDensity,
  children,
}: {
  me: Me;
  initialCollapsed: boolean;
  initialTheme: Theme;
  initialDensity: Density;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const groups = navFor(me.role);

  // Escape closes the drawer; choosing a place in it closes it too (see the links below).
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  function toggleCollapsed() {
    setCollapsed((current) => {
      applySidebar(!current);
      return !current;
    });
  }

  return (
    <MeProvider me={me}>
      <div className={styles.shell}>
        <a href="#main" className={styles.skip}>
          Skip to the content
        </a>

        <aside id="sidebar" className={`${styles.sidebar} ${drawerOpen ? styles.open : ""}`} aria-label="Main">
          <div className={styles.brand}>
            <Link href="/" className={styles.brandLink} aria-label="Daftar home">
              <IconNotebook size={24} stroke={1.5} aria-hidden />
              <span className={styles.brandName}>
                Daftar <span lang="ur" className={styles.urdu}>دفتر</span>
              </span>
            </Link>
            <button type="button" className={styles.drawerClose} onClick={() => setDrawerOpen(false)} aria-label="Close the menu">
              <IconX size={20} stroke={1.75} aria-hidden />
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
                          <item.icon size={20} stroke={1.5} aria-hidden className={styles.itemIcon} />
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
            className={styles.collapse}
            onClick={toggleCollapsed}
            aria-pressed={collapsed}
            aria-label={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
            data-tip={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
          >
            {collapsed ? <IconLayoutSidebarLeftExpand size={20} stroke={1.5} aria-hidden /> : <IconLayoutSidebarLeftCollapse size={20} stroke={1.5} aria-hidden />}
            <span className={styles.itemLabel}>Collapse</span>
          </button>
        </aside>

        {drawerOpen ? <div className={styles.scrim} onClick={() => setDrawerOpen(false)} aria-hidden /> : null}

        <div className={styles.main}>
          <header className={styles.topbar}>
            <button
              type="button"
              className={styles.menuButton}
              onClick={() => setDrawerOpen(true)}
              aria-label="Open the menu"
              aria-expanded={drawerOpen}
              aria-controls="sidebar"
            >
              <IconMenu2 size={22} stroke={1.5} aria-hidden />
            </button>
            <button
              type="button"
              className={styles.railButton}
              onClick={toggleCollapsed}
              aria-label={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
              aria-pressed={collapsed}
            >
              {collapsed ? <IconLayoutSidebarLeftExpand size={20} stroke={1.5} aria-hidden /> : <IconLayoutSidebarLeftCollapse size={20} stroke={1.5} aria-hidden />}
            </button>
            <span className={styles.spacer} />
            <ProfileMenu me={me} initialTheme={initialTheme} initialDensity={initialDensity} />
          </header>
          <main id="main" tabIndex={-1} className={styles.content}>
            {children}
          </main>
        </div>
        <Tour />
      </div>
    </MeProvider>
  );
}
