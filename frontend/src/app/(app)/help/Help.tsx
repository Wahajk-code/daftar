"use client";

import { IconRoute } from "@tabler/icons-react";
import Link from "next/link";
import { useMe } from "@/components/shell/MeContext";
import { navFor } from "@/components/shell/nav";
import { ROLE_LINE, ROLE_NAME, ROLE_TASKS } from "@/components/shell/roles";
import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { Stamp } from "@/components/ui/Stamp";
import styles from "./Help.module.css";

/**
 * The Help center: a guide written for the signed-in role, and the only place the tour can be started again. (It also
 * starts by itself the first time a person signs in.)
 */
export function Help() {
  const me = useMe();
  const groups = navFor(me.role);

  return (
    <>
      <PageHeader print={false} title="Help center" description={`A guide for ${ROLE_NAME[me.role].toLowerCase()}s: what you do here and where to find it.`} />

      <div className={styles.grid}>
        <Panel className={styles.tour}>
          <div className={styles.tourRow}>
            <span className={styles.tourIcon}>
              <IconRoute size={28} stroke={1.5} aria-hidden />
            </span>
            <div className={styles.tourText}>
              <h2>Take the guided tour</h2>
              <p className="muted">
                A short walk through the screen for {ROLE_NAME[me.role].toLowerCase()}s, with what is waiting for you right now. You can skip it at any
                step.
              </p>
            </div>
            <Button variant="primary" onClick={() => window.dispatchEvent(new Event("daftar:tour"))}>
              Start the tour
            </Button>
          </div>
        </Panel>

        <Panel title={`Your role: ${ROLE_NAME[me.role]}`}>
          <p className={styles.lead}>{ROLE_LINE[me.role]}</p>
          <ol className={styles.tasks}>
            {ROLE_TASKS[me.role].map((task) => (
              <li key={task}>{task}</li>
            ))}
          </ol>
        </Panel>

        <Panel title="How a document moves">
          <ul className={styles.flow} aria-label="The steps a document goes through">
            <li>
              <Stamp status="draft" />
              <span>Written and edited by its author</span>
            </li>
            <li>
              <Stamp status="submitted" />
              <span>Sent for approval; nobody approves their own</span>
            </li>
            <li>
              <Stamp status="approved" />
              <span>Approved; an expense or purchase can now get a voucher</span>
            </li>
            <li>
              <Stamp status="posted" />
              <span>Posted to the books and numbered; it can no longer be changed</span>
            </li>
            <li>
              <Stamp status="rejected" />
              <span>Sent back with a reason; the author fixes it and sends it again</span>
            </li>
            <li>
              <Stamp status="void" />
              <span>A posted voucher cancelled by a reversing voucher, with a reason</span>
            </li>
          </ul>
        </Panel>

        <Panel title="Your screens" className={styles.wide}>
          {groups.map((group, index) => (
            <section key={group.heading ?? index} className={styles.screens}>
              {group.heading ? <h3>{group.heading}</h3> : null}
              <ul>
                {group.items.map((item) => (
                  <li key={item.href}>
                    <Link href={item.href} className={styles.screen}>
                      <span className={styles.screenIcon}>
                        <item.icon size={22} stroke={1.5} aria-hidden />
                      </span>
                      <span className={styles.screenText}>
                        <span className={styles.screenName}>{item.label}</span>
                        <span className={styles.screenHint}>{item.hint}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </Panel>

        <Panel title="Good to know" className={styles.wide}>
          <ul className={styles.tips}>
            <li>Press anywhere on a row in a list to open it. The arrow at the end of the row says it leads somewhere.</li>
            <li>Filters, sort and page are kept in the address, so you can bookmark a view or send the link to a colleague.</li>
            <li>The New button in the top bar opens a form over the screen you are on. Escape closes it.</li>
            <li>The bell counts what is waiting for you. The sun and moon switch the theme.</li>
            <li>In the voucher editor, Tab moves across a line, and Enter in an amount goes to the next line. The footer always shows debit, credit and the difference.</li>
          </ul>
        </Panel>
      </div>
    </>
  );
}
