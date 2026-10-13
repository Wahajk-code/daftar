"use client";

import { IconChartBar, IconTable } from "@tabler/icons-react";
import { useState, type ReactNode } from "react";
import type { DocumentStatus, OverviewMonth, StatusCount } from "@/api/types";
import { compactMoney, formatMoney, formatWithCurrency, fromPaisa, niceCeiling, percentOf, toPaisa, ZERO_PAISA } from "@/lib/money";
import { statusLabel } from "@/components/ui/Stamp";
import styles from "./Charts.module.css";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-10" as "Oct". */
export function monthName(month: string): string {
  return MONTHS[Number(month.slice(5, 7)) - 1] ?? month;
}

/**
 * A view switch: the picture, or the same numbers as a table, so nothing is only in a colour or a height. The two sit on the
 * faces of a card, and pressing the button turns the card over like a playing card. The face that is turned away is inert, so
 * the keyboard and screen readers only reach the one in view.
 */
function Frame({ title, subtitle, legend, chart, table }: { title: string; subtitle?: string; legend?: ReactNode; chart: ReactNode; table: ReactNode }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <figure className={styles.frame}>
      <figcaption className={styles.head}>
        <span className={styles.titles}>
          <span className={styles.title}>{title}</span>
          {subtitle ? <span className={styles.subtitle}>{subtitle}</span> : null}
        </span>
        <button type="button" className={styles.switch} aria-pressed={asTable} onClick={() => setAsTable((current) => !current)}>
          <span className={`${styles.switchIcon} ${asTable ? styles.turned : ""}`} aria-hidden>
            <IconTable size={16} stroke={2} className={styles.iconTable} />
            <IconChartBar size={16} stroke={2} className={styles.iconChart} />
          </span>
          {asTable ? "Chart" : "Table"}
        </button>
      </figcaption>
      <div className={styles.scene}>
        <div className={`${styles.card} ${asTable ? styles.flipped : ""}`}>
          <div className={styles.face} inert={asTable} aria-hidden={asTable}>
            {legend ? <div className={styles.legend}>{legend}</div> : null}
            {chart}
          </div>
          <div className={`${styles.face} ${styles.back}`} inert={!asTable} aria-hidden={!asTable}>
            {table}
          </div>
        </div>
      </div>
    </figure>
  );
}

function Key({ color, label }: { color: string; label: string }) {
  return (
    <span className={styles.key}>
      <span className={styles.swatch} style={{ background: color }} aria-hidden />
      {label}
    </span>
  );
}

/** Month by month: expenses and purchases side by side. Heights are shares of a round axis top, worked out in whole paisa. */
export function SpendColumns({ months }: { months: OverviewMonth[] }) {
  const [active, setActive] = useState<number | null>(null);
  const values = months.map((month) => [toPaisa(month.expenses) ?? ZERO_PAISA, toPaisa(month.purchases) ?? ZERO_PAISA] as const);
  const top = niceCeiling(values.reduce((largest, [a, b]) => (a > largest ? a : b > largest ? b : largest), ZERO_PAISA));
  const ticks = [4, 3, 2, 1, 0].map((step) => (top * BigInt(step)) / BigInt(4));
  const empty = values.every(([a, b]) => a === ZERO_PAISA && b === ZERO_PAISA);

  const chart = (
    <div className={styles.columns}>
      <div className={styles.axis} aria-hidden>
        {ticks.map((tick) => (
          <span key={String(tick)} className={styles.tick}>
            {compactMoney(tick)}
          </span>
        ))}
      </div>
      <div className={styles.plot}>
        <div className={styles.grid} aria-hidden>
          {ticks.map((tick) => (
            <span key={String(tick)} />
          ))}
        </div>
        <ul className={styles.groups}>
          {months.map((month, index) => {
            const [expenses, purchases] = values[index];
            const label = `${monthName(month.month)} ${month.month.slice(0, 4)}: expenses ${formatMoney(month.expenses)}, purchases ${formatMoney(month.purchases)}`;
            return (
              <li
                key={month.month}
                className={`${styles.group} ${active === index ? styles.on : ""}`}
                tabIndex={0}
                aria-label={label}
                onPointerEnter={() => setActive(index)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(index)}
                onBlur={() => setActive(null)}
              >
                <span className={styles.bars}>
                  <span className={styles.bar} style={{ height: `${percentOf(expenses, top)}%`, background: "var(--chart-1)" }} />
                  <span className={styles.bar} style={{ height: `${percentOf(purchases, top)}%`, background: "var(--chart-2)" }} />
                </span>
                <span className={styles.month}>{monthName(month.month)}</span>
                {active === index ? (
                  <span className={styles.tip} role="status">
                    <strong>
                      {monthName(month.month)} {month.month.slice(0, 4)}
                    </strong>
                    <span>
                      <i style={{ background: "var(--chart-1)" }} /> Expenses {formatWithCurrency(month.expenses)}
                      <small> ({month.expense_count})</small>
                    </span>
                    <span>
                      <i style={{ background: "var(--chart-2)" }} /> Purchases {formatWithCurrency(month.purchases)}
                      <small> ({month.purchase_count})</small>
                    </span>
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
        {empty ? <p className={styles.note}>Nothing approved or posted in these months yet.</p> : null}
      </div>
    </div>
  );

  const table = (
    <table className={styles.table}>
      <caption className="sr-only">Approved and posted spend by month</caption>
      <thead>
        <tr>
          <th scope="col">Month</th>
          <th scope="col" className="num">Expenses (PKR)</th>
          <th scope="col" className="num">Purchases (PKR)</th>
        </tr>
      </thead>
      <tbody>
        {months.map((month) => (
          <tr key={month.month}>
            <th scope="row">
              {monthName(month.month)} {month.month.slice(0, 4)}
            </th>
            <td className="num">{formatMoney(month.expenses)}</td>
            <td className="num">{formatMoney(month.purchases)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <Frame
      title="Spend by month"
      subtitle="Approved and posted, by document date. Amounts in PKR"
      legend={
        <>
          <Key color="var(--chart-1)" label="Expenses" />
          <Key color="var(--chart-2)" label="Purchases (gross)" />
        </>
      }
      chart={chart}
      table={table}
    />
  );
}

const STATUS_COLOR: Record<DocumentStatus, string> = {
  draft: "var(--slate)",
  submitted: "var(--caution)",
  approved: "var(--info)",
  rejected: "var(--negative)",
  posted: "var(--positive)",
  void: "var(--text-3)",
};

/** Where documents stand: one stacked bar per kind, a segment per status, a 2px gap between segments. */
export function StatusBars({ rows }: { rows: Array<{ label: string; counts: StatusCount[] }> }) {
  const present = new Set(rows.flatMap((row) => row.counts.filter((count) => count.count > 0).map((count) => count.status)));
  const order = rows[0]?.counts.map((count) => count.status) ?? [];

  const chart = (
    <ul className={styles.stacks}>
      {rows.map((row) => {
        const total = row.counts.reduce((sum, count) => sum + count.count, 0);
        return (
          <li key={row.label} className={styles.stack}>
            <span className={styles.stackLabel}>
              {row.label}
              <small>{total}</small>
            </span>
            <span className={styles.track} role="img" aria-label={`${row.label}: ${row.counts.filter((c) => c.count > 0).map((c) => `${c.count} ${statusLabel(c.status).toLowerCase()}`).join(", ") || "none"}`}>
              {total === 0 ? (
                <span className={styles.none}>None yet</span>
              ) : (
                row.counts
                  .filter((count) => count.count > 0)
                  .map((count) => (
                    <span
                      key={count.status}
                      className={styles.segment}
                      style={{ flexGrow: count.count, background: STATUS_COLOR[count.status] }}
                      title={`${statusLabel(count.status)}: ${count.count}`}
                    />
                  ))
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );

  const table = (
    <table className={styles.table}>
      <caption className="sr-only">Documents by status</caption>
      <thead>
        <tr>
          <th scope="col">Status</th>
          {rows.map((row) => (
            <th key={row.label} scope="col" className="num">
              {row.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {order.map((status) => (
          <tr key={status}>
            <th scope="row">{statusLabel(status)}</th>
            {rows.map((row) => (
              <td key={row.label} className="num">
                {row.counts.find((count) => count.status === status)?.count ?? 0}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <Frame
      title="Where documents stand"
      subtitle="Every document, by status"
      legend={order.filter((status) => present.has(status)).map((status) => <Key key={status} color={STATUS_COLOR[status]} label={statusLabel(status)} />)}
      chart={chart}
      table={table}
    />
  );
}

/** A ranked list as horizontal bars, one colour, the value at the tip. */
export function RankedBars({ title, subtitle, rows, empty }: { title: string; subtitle?: string; rows: Array<{ label: string; value: string }>; empty: string }) {
  const paisa = rows.map((row) => toPaisa(row.value) ?? ZERO_PAISA);
  const largest = paisa.reduce((top, value) => (value > top ? value : top), ZERO_PAISA);

  const chart =
    rows.length === 0 ? (
      <p className={styles.note}>{empty}</p>
    ) : (
      <ul className={styles.ranked}>
        {rows.map((row, index) => (
          <li key={row.label}>
            <span className={`${styles.rankLabel} clip`} title={row.label}>
              {row.label}
            </span>
            <span className={styles.rankTrack} aria-hidden>
              <span className={styles.rankBar} style={{ width: `${percentOf(paisa[index], largest)}%` }} />
            </span>
            <span className={`${styles.rankValue} num`}>{formatWithCurrency(fromPaisa(paisa[index]))}</span>
          </li>
        ))}
      </ul>
    );

  const table = (
    <table className={styles.table}>
      <caption className="sr-only">{title}</caption>
      <thead>
        <tr>
          <th scope="col">Name</th>
          <th scope="col" className="num">Amount (PKR)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <th scope="row">{row.label}</th>
            <td className="num">{formatMoney(row.value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return <Frame title={title} subtitle={subtitle} chart={chart} table={table} />;
}
