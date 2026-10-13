"use client";

import { Joyride, EVENTS, STATUS, type EventData, type Step, type TooltipRenderProps } from "react-joyride";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "@/api/client";
import type { Me, Role } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { useWorkQueues } from "@/lib/queues";
import { useMe } from "./MeContext";
import { ROLE_LINE, ROLE_NAME } from "./roles";
import { useCreate } from "./CreateModal";
import styles from "./Tour.module.css";

interface Plain {
  title: string;
  body: ReactNode;
  /** A selector in the page, or nothing for a card in the middle of the screen. */
  target?: string;
  /** Needs the sidebar on screen, which is off to the side on a phone. */
  sidebar?: boolean;
}

const ROLE_ARTICLE: Record<Role, string> = { admin: "an Admin", accountant: "an Accountant", approver: "an Approver", staff: "a member of staff" };

const FIRST_NAME = (me: Me) => me.full_name.split(/\s+/)[0] ?? me.full_name;

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** The role's own step in the sidebar. */
/** The places in the sidebar that matter most to each role, in the order their work usually goes. */
const NAV_STEPS: Record<Role, Plain[]> = {
  staff: [
    { title: "Your expenses", body: "Every expense you wrote, and where it stands. If one is sent back, the reason is in its history and at the top of the expense.", target: '[data-tour="nav-expenses"]', sidebar: true },
  ],
  approver: [
    { title: "Approvals", body: "Documents other people sent for approval collect here. Open one, check the receipt, then approve or reject it with a comment. Drafts stay hidden from you until their author sends them.", target: '[data-tour="nav-approvals"]', sidebar: true },
    { title: "Reports", body: "See where the money went, by cost centre and by vendor, and download it as a spreadsheet.", target: '[data-tour="nav-reports"]', sidebar: true },
  ],
  accountant: [
    { title: "Purchases", body: "Enter vendor invoices and memos. The tax is worked out for you as you type.", target: '[data-tour="nav-purchases"]', sidebar: true },
    { title: "Vouchers", body: "Generate a payment voucher from an approved expense or purchase, check its lines, send it, and post it once it is approved.", target: '[data-tour="nav-vouchers"]', sidebar: true },
    { title: "Accounting settings", body: "Choose where generated vouchers post and when the numbering year starts.", target: '[data-tour="nav-settings"]', sidebar: true },
  ],
  admin: [
    { title: "People", body: "Invite people by email and choose their role, change a role, or switch an account off. You never see or set anyone's password.", target: '[data-tour="nav-users"]', sidebar: true },
    { title: "Approvals", body: "You can decide what is waiting too, when the approvers are away.", target: '[data-tour="nav-approvals"]', sidebar: true },
    { title: "Audit log", body: "Who changed what, and when. Nothing here can be edited or removed.", target: '[data-tour="nav-audit"]', sidebar: true },
  ],
};

/**
 * The first-use tour, written for the person taking it: their name and role, and what is waiting for them right now. It
 * starts by itself for someone who has not seen it (the server remembers, so it follows them across devices), can be
 * skipped at every step, closes on Escape, and can be started again only from the Help center. Finishing or skipping is
 * saved on the server. The tour library does the spotlight, the placement and the focus trap; the card is ours.
 */
export function Tour() {
  const me = useMe();
  const create = useCreate();
  const queues = useWorkQueues(me).filter((queue) => queue.attention);
  const waiting = queues.reduce((total, queue) => total + (queue.items?.length ?? 0), 0);
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
    }, 900);
    return () => window.clearTimeout(timer);
  }, [me.tour_completed_at]);

  // "Take the tour" in the Help center.
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
    const opening: Plain = {
      title: `Welcome, ${FIRST_NAME(me)}`,
      body: (
        <>
          <p>
            You are signed in as {ROLE_ARTICLE[me.role]}. {ROLE_LINE[me.role]}
          </p>
          <p className={styles.live}>
            {waiting > 0 ? `Right now ${plural(waiting, "thing needs", "things need")} you.` : "Nothing needs you right now."}
          </p>
        </>
      ),
    };
    const sidebar: Plain = {
      title: "Everything you can open is here",
      body: "The menu shows only what your role may use. The arrow at its foot folds it to a strip of icons to give the screens more room.",
      target: "#sidebar",
      sidebar: true,
    };
    const make: Plain | null = create.allowed.length
      ? {
          title: "Start something new",
          body:
            me.role === "staff"
              ? "Press New to write an expense. It opens over the screen you are on, so you never lose your place. Attach the receipt, save it, then send it for approval."
              : `Press New to start ${create.allowed.includes("voucher") ? "an expense, a purchase, a voucher or an invitation" : "a document"}. It opens over the screen you are on, so you never lose your place.`,
          target: '[data-tour="new"]',
        }
      : null;
    const bell: Plain = {
      title: "What is waiting for you",
      body:
        waiting > 0
          ? `The bell counts the things that need you: ${plural(waiting, "item", "items")} today. Press it to jump straight to one.`
          : "The bell counts the things that need you, such as documents to decide or vouchers to post. It is empty now; it fills as work arrives.",
      target: '[data-tour="bell"]',
    };
    const look: Plain = {
      title: "Light or dark",
      body: "Switch between the light and dark theme here, whichever is easier on your eyes.",
      target: '[data-tour="theme"]',
    };
    const finish: Plain = {
      title: `That is the tour, ${FIRST_NAME(me)}`,
      body: `Whenever you need a reminder, open the Help center with the question mark. It has a guide written for your role (${ROLE_NAME[me.role]}), how a document moves, and where to take this tour again.`,
      target: '[data-tour="help"]',
    };

    const plain = [opening, sidebar, ...NAV_STEPS[me.role], ...(make ? [make] : []), bell, look, finish].filter((step) => !(narrow && step.sidebar));
    return plain.map((step, index) => ({
      id: `step-${index}`,
      target: step.target ?? "body",
      placement: step.target ? (step.sidebar ? "right" : "bottom") : "center",
      title: step.title,
      content: (
        <div className={styles.content}>
          <p className={styles.progress}>
            Step {index + 1} of {plain.length}
          </p>
          <div className={styles.body}>{step.body}</div>
        </div>
      ),
    }));
  }, [me, waiting, create.allowed, narrow]);

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
      tooltipComponent={TourCard}
      options={{
        skipBeacon: true,
        dismissKeyAction: false,
        overlayClickAction: false,
        overlayColor: "color-mix(in srgb, var(--k-tour-scrim) 55%, transparent)",
        arrowColor: "var(--bg-surface)",
        zIndex: 90,
        spotlightRadius: 16,
        width: 380,
      }}
    />
  );
}

/** The tour's card: a white rounded sheet with clear Back, Skip and Next buttons, in the same style as the rest of the app. */
function TourCard({ backProps, primaryProps, skipProps, tooltipProps, index, isLastStep, step }: TooltipRenderProps) {
  return (
    <div {...tooltipProps} className={styles.card}>
      {step.title ? <h2 className={styles.title}>{step.title}</h2> : null}
      {step.content}
      <div className={styles.footer}>
        <Button {...skipProps} variant="quiet" small>
          Skip the tour
        </Button>
        <span className={styles.spacer} />
        {index > 0 ? (
          <Button {...backProps} small>
            Back
          </Button>
        ) : null}
        <Button {...primaryProps} variant="primary" small>
          {isLastStep ? "Done" : "Next"}
        </Button>
      </div>
    </div>
  );
}
