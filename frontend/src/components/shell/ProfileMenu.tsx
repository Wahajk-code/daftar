"use client";

import { IconHelpCircle, IconKey, IconLogout } from "@tabler/icons-react";
import Link from "next/link";
import { useState } from "react";
import type { Me } from "@/api/types";
import { Dropdown } from "@/components/ui/Dropdown";
import { navigate } from "@/lib/navigate";
import { ROLE_NAME } from "./roles";
import styles from "./ProfileMenu.module.css";

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "")).toUpperCase();
}

/** The person's menu: who they are, help, their password, and signing out. The look of the app is set from the top bar. */
export function ProfileMenu({ me }: { me: Me }) {
  const [leaving, setLeaving] = useState(false);

  async function signOut() {
    setLeaving(true);
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    } finally {
      navigate("/login");
    }
  }

  return (
    <Dropdown
      label={`Account menu for ${me.full_name}`}
      triggerClassName={styles.trigger}
      dataTour="profile"
      width="290px"
      trigger={
        <>
          <span className={styles.avatar} aria-hidden>
            {initials(me.full_name)}
          </span>
          <span className={styles.who}>
            <span className={styles.name}>{me.full_name}</span>
            <span className={styles.role}>{ROLE_NAME[me.role]}</span>
          </span>
        </>
      }
    >
      {(close) => (
        <>
          <div className={styles.identity}>
            <p className={styles.name}>{me.full_name}</p>
            <p className={styles.email}>{me.email}</p>
            <p className={styles.roleLine}>{ROLE_NAME[me.role]}</p>
          </div>
          <div className={styles.links}>
            <Link href="/help" onClick={close}>
              <IconHelpCircle size={20} stroke={1.5} aria-hidden />
              Help center
            </Link>
            <Link href="/profile" onClick={close}>
              <IconKey size={20} stroke={1.5} aria-hidden />
              Change your password
            </Link>
            <button type="button" onClick={signOut} disabled={leaving} aria-busy={leaving || undefined}>
              <IconLogout size={20} stroke={1.5} aria-hidden />
              {leaving ? "Signing out" : "Sign out"}
            </button>
          </div>
        </>
      )}
    </Dropdown>
  );
}
