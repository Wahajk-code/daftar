"use client";

import { IconCamera } from "@tabler/icons-react";
import { useCreate } from "./CreateModal";
import styles from "./CaptureButton.module.css";

/**
 * On a phone, the quickest way to record an expense: one round button, always in reach, that opens the camera. The photo
 * becomes a new expense with the receipt already attached. It is drawn only for roles that may write expenses, and only on a
 * narrow screen (a computer has the New menu).
 */
export function CaptureButton() {
  const create = useCreate();
  if (!create.allowed.includes("expense")) return null;
  return (
    <button type="button" className={styles.button} onClick={create.capture} aria-label="Take a photo of a receipt" data-noprint>
      <IconCamera size={28} stroke={1.75} aria-hidden />
    </button>
  );
}
