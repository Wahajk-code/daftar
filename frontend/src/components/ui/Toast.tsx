"use client";

import { IconCheck, IconX, IconAlertTriangle } from "@tabler/icons-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import styles from "./Toast.module.css";

type Tone = "success" | "error";
interface ToastItem {
  id: number;
  tone: Tone;
  text: string;
  reference?: string;
}

interface ToastApi {
  success: (text: string) => void;
  /** `reference` is the correlation id the API gave, shown so a person can quote it. */
  error: (text: string, reference?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast needs a ToastProvider");
  return context;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => setItems((current) => current.filter((item) => item.id !== id)), []);
  const push = useCallback(
    (tone: Tone, text: string, reference?: string) => {
      const id = ++counter.current;
      setItems((current) => [...current.slice(-3), { id, tone, text, reference }]);
      window.setTimeout(() => dismiss(id), tone === "error" ? 9000 : 5000);
    },
    [dismiss],
  );
  const api = useMemo<ToastApi>(
    () => ({ success: (text) => push("success", text), error: (text, reference) => push("error", text, reference) }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className={styles.region} role="region" aria-label="Notifications">
        {items.map((item) => (
          <div key={item.id} className={`${styles.toast} ${styles[item.tone]}`} role={item.tone === "error" ? "alert" : "status"}>
            {item.tone === "success" ? <IconCheck size={20} stroke={1.75} aria-hidden /> : <IconAlertTriangle size={20} stroke={1.75} aria-hidden />}
            <div className={styles.body}>
              <p>{item.text}</p>
              {item.reference ? <p className={styles.reference}>Reference {item.reference}</p> : null}
            </div>
            <button type="button" className={styles.close} onClick={() => dismiss(item.id)} aria-label="Dismiss notification">
              <IconX size={18} stroke={1.75} aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
