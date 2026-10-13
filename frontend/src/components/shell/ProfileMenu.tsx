"use client";

import { IconDeviceDesktop, IconKey, IconLogout, IconMoon, IconRoute, IconSun } from "@tabler/icons-react";
import Link from "next/link";
import { useId, useRef, useState } from "react";
import type { Me } from "@/api/types";
import { useToast } from "@/components/ui/Toast";
import { navigate } from "@/lib/navigate";
import { applyDensity, applyTheme, type Density, type Theme } from "@/lib/preferences";
import styles from "./ProfileMenu.module.css";

const ROLE_NAMES: Record<Me["role"], string> = {
  admin: "Admin",
  accountant: "Accountant",
  approver: "Approver",
  staff: "Staff",
};

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "")).toUpperCase();
}

/** The person's menu: who they are, how the app looks for them, the tour, their password, and signing out. */
export function ProfileMenu({ me, initialTheme, initialDensity }: { me: Me; initialTheme: Theme; initialDensity: Density }) {
  const menuId = useId();
  const menu = useRef<HTMLDivElement>(null);
  const toast = useToast();
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [density, setDensity] = useState<Density>(initialDensity);
  const [leaving, setLeaving] = useState(false);

  function close() {
    menu.current?.hidePopover?.();
  }

  async function signOut() {
    setLeaving(true);
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    } finally {
      navigate("/login");
    }
  }

  function chooseTheme(next: Theme) {
    applyTheme(next);
    setTheme(next);
  }

  function chooseDensity(next: Density) {
    applyDensity(next);
    setDensity(next);
    toast.success(next === "compact" ? "Compact rows on" : "Comfortable rows on");
  }

  return (
    <>
      <button type="button" className={styles.trigger} popoverTarget={menuId} data-tour="profile" aria-label={`Account menu for ${me.full_name}`}>
        <span className={styles.avatar} aria-hidden>
          {initials(me.full_name)}
        </span>
        <span className={styles.who}>
          <span className={styles.name}>{me.full_name}</span>
          <span className={styles.role}>{ROLE_NAMES[me.role]}</span>
        </span>
      </button>

      <div id={menuId} ref={menu} popover="auto" className={styles.menu}>
        <div className={styles.identity}>
          <p className={styles.name}>{me.full_name}</p>
          <p className={styles.email}>{me.email}</p>
          <p className={styles.roleLine}>{ROLE_NAMES[me.role]}</p>
        </div>

        <fieldset className={styles.group}>
          <legend>Theme</legend>
          <div className={styles.segments}>
            {(
              [
                ["system", "System", IconDeviceDesktop],
                ["light", "Light", IconSun],
                ["dark", "Dark", IconMoon],
              ] as const
            ).map(([value, label, Icon]) => (
              <button key={value} type="button" aria-pressed={theme === value} onClick={() => chooseTheme(value)}>
                <Icon size={16} stroke={1.5} aria-hidden />
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className={styles.group}>
          <legend>Row density</legend>
          <div className={styles.segments}>
            {(
              [
                ["compact", "Compact"],
                ["comfortable", "Comfortable"],
              ] as const
            ).map(([value, label]) => (
              <button key={value} type="button" aria-pressed={density === value} onClick={() => chooseDensity(value)}>
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        <div className={styles.links}>
          <button
            type="button"
            onClick={() => {
              close();
              window.dispatchEvent(new Event("daftar:tour"));
            }}
          >
            <IconRoute size={18} stroke={1.5} aria-hidden />
            Take the tour
          </button>
          <Link href="/profile" onClick={close}>
            <IconKey size={18} stroke={1.5} aria-hidden />
            Change your password
          </Link>
          <button type="button" onClick={signOut} disabled={leaving} aria-busy={leaving || undefined}>
            <IconLogout size={18} stroke={1.5} aria-hidden />
            {leaving ? "Signing out" : "Sign out"}
          </button>
        </div>
      </div>
    </>
  );
}
