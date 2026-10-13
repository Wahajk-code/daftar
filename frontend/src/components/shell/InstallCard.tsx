"use client";

import { IconDeviceMobile } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Panel } from "@/components/ui/Layout";
import styles from "./InstallCard.module.css";

interface InstallPrompt extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

/**
 * Put Daftar on a phone's home screen. Where the browser offers an install button it is drawn here; where it does not (iPhone),
 * the steps are written out. Once installed, it opens full screen like an app and the camera button is one tap away.
 */
export function InstallCard() {
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setPrompt(event as InstallPrompt);
    };
    const onInstalled = () => setInstalled(true);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  return (
    <Panel title="Use it on your phone" className={styles.card}>
      <div className={styles.body}>
        <span className={styles.icon}>
          <IconDeviceMobile size={26} stroke={1.5} aria-hidden />
        </span>
        <div className={styles.text}>
          <p>
            Install Daftar on your home screen and it opens full screen like an app. On a phone, a round camera button is always in
            reach: take a photo of a receipt and the expense starts with it attached.
          </p>
          <ul>
            <li>
              <strong>Android (Chrome):</strong> the menu, then Install app.
            </li>
            <li>
              <strong>iPhone (Safari):</strong> the Share button, then Add to Home Screen.
            </li>
          </ul>
          {installed ? <p className={styles.done}>It is installed on this device.</p> : null}
          {prompt && !installed ? (
            <Button
              variant="primary"
              onClick={async () => {
                await prompt.prompt();
                await prompt.userChoice;
                setPrompt(null);
              }}
            >
              Install on this device
            </Button>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
