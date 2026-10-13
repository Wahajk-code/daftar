"use client";

import { Joyride, EVENTS, STATUS, type EventData, type Step } from "react-joyride";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "@/api/client";
import type { Role } from "@/api/types";
import { useMe } from "./MeContext";

interface Plain {
  title: string;
  body: ReactNode;
  /** A data-tour value in the page, or nothing for a card in the middle of the screen. */
  target?: string;
  /** Needs the sidebar on screen, which is off to the side on a phone. */
  sidebar?: boolean;
}

const OPENING: Plain = {
  title: "Welcome to Daftar",
  body: "A short look at where things are. Skip it any time with the Skip button or the Escape key; it will not come back unless you ask for it from your account menu.",
};

const SIDEBAR: Plain = {
  title: "Everything you can open is here",
  body: "The menu shows only what your role may use. The button at the bottom folds it to a strip of icons to give the screens more room.",
  target: "#sidebar",
  sidebar: true,
};

const BY_ROLE: Record<Role, Plain[]> = {
  staff: [
    { title: "Add an expense", body: "Write what it was for, attach the receipt, and send it for approval. If it comes back, the reason is in its history.", target: '[data-tour="nav-expenses"]', sidebar: true },
    { title: "Your home screen", body: "It lists what is sent back to you, your drafts, and what is waiting for approval.", target: "#main" },
  ],
  approver: [
    { title: "Decide what is waiting", body: "Documents other people sent for approval collect here. Open one to read it, look at the receipt, and approve or reject it with a comment.", target: '[data-tour="nav-approvals"]', sidebar: true },
    { title: "Your home screen", body: "It shows what is waiting for your decision, and this month's spend by cost centre.", target: "#main" },
  ],
  accountant: [
    { title: "Turn approved items into vouchers", body: "Open an approved expense or purchase and generate its payment voucher. Check the lines, send it, and post it when it is approved.", target: '[data-tour="nav-vouchers"]', sidebar: true },
    { title: "Your home screen", body: "It lists approved items that still need a voucher, vouchers ready to post, and your unfinished ones.", target: "#main" },
  ],
  admin: [
    { title: "Manage the people", body: "Invite people by email and choose their role, change a role, or switch an account off. You never see or set anyone's password.", target: '[data-tour="nav-users"]', sidebar: true },
    { title: "Your home screen", body: "It shows what is waiting for a decision and what is ready to post, the same lists the approvers and accountants work from.", target: "#main" },
  ],
};

const ACCOUNT: Plain = {
  title: "Your account menu",
  body: "Choose a light or dark theme, the row density, change your password, or take this tour again.",
  target: '[data-tour="profile"]',
};

/**
 * The first-use tour. It starts by itself for someone who has not seen it (the server remembers, so it follows them across
 * devices), can be skipped at every step, closes on Escape, and is started again from the account menu. Finishing or
 * skipping is saved on the server. The tour library does the spotlight, the placement and the focus trap.
 */
export function Tour() {
  const me = useMe();
  const [run, setRun] = useState(false);
  const [narrow, setNarrow] = useState(false);
  const started = useRef(false);

  const finish = useCallback(() => {
    setRun(false);
    api("/me/tour/complete", { method: "POST" }).catch(() => undefined);
  }, []);

  // Start for someone who has not seen it, once the screen has been drawn.
  useEffect(() => {
    if (me.tour_completed_at !== null || started.current) return;
    started.current = true;
    const timer = window.setTimeout(() => {
      setNarrow(window.matchMedia("(max-width: 900px)").matches);
      setRun(true);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [me.tour_completed_at]);

  // "Take the tour" in the account menu.
  useEffect(() => {
    const restart = () => {
      setNarrow(window.matchMedia("(max-width: 900px)").matches);
      setRun(true);
    };
    window.addEventListener("daftar:tour", restart);
    return () => window.removeEventListener("daftar:tour", restart);
  }, []);

  // Escape ends the whole tour, from any step (the library's own Escape handling only closes one step).
  useEffect(() => {
    if (!run) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && finish();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [run, finish]);

  const steps = useMemo<Step[]>(() => {
    const plain = [OPENING, SIDEBAR, ...BY_ROLE[me.role], ACCOUNT].filter((step) => !(narrow && step.sidebar));
    return plain.map((step, index) => ({
      id: `step-${index}`,
      target: step.target ?? "body",
      placement: step.target ? (step.target === "#main" ? "bottom" : step.sidebar ? "right" : "bottom-end") : "center",
      title: step.title,
      content: (
        <div>
          <p style={{ marginBottom: 6, fontSize: 12, color: "var(--text-3)" }}>
            Step {index + 1} of {plain.length}
          </p>
          <p>{step.body}</p>
        </div>
      ),
    }));
  }, [me.role, narrow]);

  const onEvent = useCallback(
    (data: EventData) => {
      const ended = data.status === STATUS.FINISHED || data.status === STATUS.SKIPPED;
      if (ended && (data.type === EVENTS.TOUR_END || data.type === EVENTS.TOUR_STATUS)) finish();
    },
    [finish],
  );

  return (
    <Joyride
      run={run}
      steps={steps}
      continuous
      onEvent={onEvent}
      scrollToFirstStep
      locale={{ back: "Back", close: "Close", last: "Done", next: "Next", nextWithProgress: "Next", skip: "Skip the tour" }}
      options={{
        buttons: ["back", "skip", "primary"],
        showProgress: false,
        skipBeacon: true,
        dismissKeyAction: false,
        overlayClickAction: false,
        primaryColor: "var(--accent)",
        backgroundColor: "var(--bg-raised)",
        textColor: "var(--text-1)",
        overlayColor: "color-mix(in srgb, var(--k-tour-scrim) 55%, transparent)",
        arrowColor: "var(--bg-raised)",
        zIndex: 90,
        spotlightRadius: 4,
        width: 360,
      }}
    />
  );
}
