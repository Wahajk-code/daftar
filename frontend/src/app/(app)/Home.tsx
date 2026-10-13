"use client";

import { IconCircleCheck } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/api/client";
import type { ExpenseReport, Overview, Page, VoucherRegisterRow } from "@/api/types";
import { RankedBars, SpendColumns, StatusBars } from "@/components/charts/Charts";
import { useMe, useZone } from "@/components/shell/MeContext";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { DateText, Money, TwoLine } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { CardGrid, Section } from "@/components/ui/Section";
import { Skeleton, SkeletonCard } from "@/components/ui/States";
import { StatCard } from "@/components/ui/StatCard";
import { Stamp } from "@/components/ui/Stamp";
import { Typewriter } from "@/components/ui/Typewriter";
import { KIND_LABEL, href } from "@/lib/documents";
import { formatDate, startOfMonth, todayInZone } from "@/lib/dates";
import { ZERO_PAISA, formatWithCurrency, fromPaisa, sumAmounts, toPaisa } from "@/lib/money";
import { useWorkQueues, type QueueItem, type WorkQueue } from "@/lib/queues";
import styles from "./Home.module.css";

const columns: Column<QueueItem>[] = [
  {
    key: "title",
    header: "What",
    primary: true,
    cell: (item) => <TwoLine title={item.title} sub={`${KIND_LABEL[item.kind].singular} by ${item.by}`} />,
    title: (item) => item.title,
    maxWidth: "30ch",
  },
  { key: "date", header: "Dated", cell: (item) => <DateText value={item.date} />, width: "112px" },
  { key: "amount", header: "Amount", numeric: true, cell: (item) => <Money value={item.amount} />, width: "120px" },
  { key: "status", header: "Status", cell: (item) => <Stamp status={item.status} />, width: "124px" },
];

/** The most that is shown of a list on the home screen; the rest is a click away. */
const SHOWN = 6;

/** One list the person works from, as a card. */
function QueueCard({ queue }: { queue: WorkQueue }) {
  const count = queue.items?.length;
  return (
    <Panel
      title={
        <span className={styles.queueTitle}>
          {queue.title}
          {count !== undefined ? <span className={`${styles.badge} ${queue.attention && count > 0 ? styles.hot : ""}`}>{count}</span> : null}
        </span>
      }
      actions={queue.viewAll ? <Link href={queue.viewAll.href}>{queue.viewAll.label}</Link> : undefined}
      flush
    >
      {queue.description ? <p className={styles.note}>{queue.description}</p> : null}
      <DataTable
        caption={queue.title}
        columns={columns}
        rows={queue.items?.slice(0, SHOWN)}
        getKey={(item) => item.key}
        rowHref={(item) => href(item.kind, item.id)}
        loading={queue.loading}
        error={queue.error}
        empty={{ title: queue.empty }}
      />
      {count !== undefined && count > SHOWN ? <p className={styles.more}>and {count - SHOWN} more. Open the full list to see them.</p> : null}
    </Panel>
  );
}

/** What replaces the lists that have nothing in them: one slim card that says so, instead of a row of empty tables. */
function AllClear({ queues }: { queues: WorkQueue[] }) {
  return (
    <Panel>
      <div className={styles.clear}>
        <IconCircleCheck size={30} stroke={1.5} aria-hidden className={styles.clearIcon} />
        <div>
          <p className={styles.clearTitle}>All clear</p>
          <p className={styles.clearText}>Nothing is waiting in: {queues.map((queue) => queue.title.toLowerCase()).join(", ")}.</p>
        </div>
      </div>
    </Panel>
  );
}

/** Figures for the month so far, from the same reports the Reports screen shows. For the office roles only. */
function useMonth(enabled: boolean) {
  const zone = useZone();
  const today = todayInZone(zone);
  const range = { date_from: startOfMonth(today), date_to: today };
  const overview = useQuery({
    queryKey: ["report", "overview", 6],
    queryFn: () => api<Overview>("/reports/overview", { query: { months: 6 } }),
    enabled,
  });
  const expenses = useQuery({
    queryKey: ["report", "expenses", range],
    queryFn: () => api<ExpenseReport>("/reports/expenses", { query: range }),
    enabled,
  });
  const posted = useQuery({
    queryKey: ["report", "register", range],
    queryFn: () => api<Page<VoucherRegisterRow>>("/reports/vouchers", { query: { ...range, statuses: ["posted"], limit: 1 } }),
    enabled,
  });
  return { overview, expenses, posted };
}

function MonthSection() {
  const { overview, posted } = useMonth(true);
  const current = overview.data?.months.at(-1);
  const spent = current ? sumAmounts([current.expenses, current.purchases]) : undefined;
  return (
    <Section id="month" title="This month" description="Approved and posted documents dated this month.">
      <CardGrid min={230}>
        <StatCard dark hero label="Spent this month" value={spent === undefined ? "" : formatWithCurrency(spent)} hint="Expenses and purchases together" loading={overview.isPending} />
        <StatCard label="Expenses" href="/reports?report=expenses" value={current?.expense_count ?? ""} hint={current ? formatWithCurrency(current.expenses) : undefined} loading={overview.isPending} />
        <StatCard label="Purchases" href="/reports?report=purchases" value={current?.purchase_count ?? ""} hint={current ? formatWithCurrency(current.purchases) : undefined} loading={overview.isPending} />
        <StatCard label="Vouchers posted" href="/vouchers?status=posted" value={posted.data?.total ?? ""} hint="Numbered and in the books" loading={posted.isPending} />
      </CardGrid>
    </Section>
  );
}

/** Where a chart will be: bars that shimmer while it loads, or the reason it did not. */
function ChartPlaceholder({ error }: { error: unknown }) {
  if (error) return <p className="muted">This chart could not be loaded. Reload the page to try again.</p>;
  return (
    <div className={styles.placeholder} role="status" aria-live="polite">
      <Skeleton width="40%" />
      <div className={styles.placeholderBars} aria-hidden>
        {[55, 80, 40, 95, 65, 75].map((height, index) => (
          <Skeleton key={index} width="100%" height={`${height}%`} block />
        ))}
      </div>
      <span className="sr-only">Loading the chart</span>
    </div>
  );
}

function TrendsSection() {
  const { overview, expenses } = useMonth(true);

  const byCentre = new Map<string, bigint>();
  for (const row of expenses.data?.rows ?? []) {
    const name = row.cost_center_name ? row.cost_center_name : "No cost centre";
    byCentre.set(name, (byCentre.get(name) ?? ZERO_PAISA) + (toPaisa(row.amount) ?? ZERO_PAISA));
  }
  const ranked = [...byCentre.entries()].sort((a, b) => (b[1] > a[1] ? 1 : b[1] < a[1] ? -1 : 0)).slice(0, 6);

  return (
    <Section id="trends" title="Trends" description="Where the money went, and where documents stand.">
      <CardGrid min={520} className={styles.trends}>
        <Panel>
          <div className={styles.chartBody}>{overview.data ? <SpendColumns months={overview.data.months} /> : <ChartPlaceholder error={overview.error} />}</div>
        </Panel>
        <Panel>
          <div className={styles.chartBody}>
            {overview.data ? (
              <StatusBars
                rows={[
                  { label: "Expenses", counts: overview.data.expense_statuses },
                  { label: "Purchases", counts: overview.data.purchase_statuses },
                  { label: "Vouchers", counts: overview.data.voucher_statuses },
                ]}
              />
            ) : (
              <ChartPlaceholder error={overview.error} />
            )}
          </div>
        </Panel>
      </CardGrid>
      <CardGrid min={520}>
        <Panel>
          <div className={styles.chartBody}>
            {expenses.data ? (
              <RankedBars
                title="Spend by cost centre"
                subtitle="This month, approved and posted expenses"
                rows={ranked.map(([label, paisa]) => ({ label, value: fromPaisa(paisa) }))}
                empty="Nothing has been approved this month yet."
              />
            ) : (
              <ChartPlaceholder error={expenses.error} />
            )}
          </div>
        </Panel>
      </CardGrid>
    </Section>
  );
}

export function Home() {
  const me = useMe();
  const zone = useZone();
  const office = me.role !== "staff";
  const queues = useWorkQueues(me);
  const first = me.full_name.split(/\s+/)[0] ?? me.full_name;

  const loading = queues.some((queue) => queue.loading);
  const hasItems = (queue: WorkQueue) => (queue.items?.length ?? 0) > 0;
  // Lists that need this person come first, and a list with nothing in it never takes a card of its own.
  const urgent = queues.filter((queue) => queue.attention);
  const urgentFull = urgent.filter(hasItems);
  const urgentEmpty = urgent.filter((queue) => !hasItems(queue) && !queue.loading);
  const other = queues.filter((queue) => !queue.attention);
  const otherFull = other.filter((queue) => hasItems(queue) || queue.loading);
  const otherEmpty = other.filter((queue) => !hasItems(queue) && !queue.loading);
  const waiting = urgentFull.reduce((total, queue) => total + (queue.items?.length ?? 0), 0);

  const attention = (
    <Section
      id="attention"
      title="Needs your attention"
      description={waiting > 0 ? "Open one to read it and act." : "Nothing is waiting for you right now."}
      count={loading ? undefined : waiting}
      urgent
    >
      {queues.length === 0 || (loading && urgentFull.length === 0) ? (
        <CardGrid min={560}>
          <SkeletonCard height="220px" />
        </CardGrid>
      ) : (
        <CardGrid min={560}>
          {urgentFull.map((queue) => (
            <QueueCard key={queue.key} queue={queue} />
          ))}
          {urgentEmpty.length > 0 ? <AllClear queues={urgentEmpty} /> : null}
        </CardGrid>
      )}
    </Section>
  );

  const progress =
    otherFull.length > 0 || otherEmpty.length > 0 ? (
      <Section id="progress" title={office ? "Your work in progress" : "Your expenses"} description="What you have started and where it stands.">
        <CardGrid min={560}>
          {otherFull.map((queue) => (
            <QueueCard key={queue.key} queue={queue} />
          ))}
          {otherEmpty.length > 0 ? <AllClear queues={otherEmpty} /> : null}
        </CardGrid>
      </Section>
    ) : null;

  return (
    <>
      <PageHeader
        title={<Typewriter text={`Welcome back, ${first}`} />}
        description={`Today is ${formatDate(todayInZone(zone))}. ${waiting > 0 ? "Here is what needs you first." : "Here is how the month is going."}`}
      />
      <div className={styles.page}>
        {office ? <MonthSection /> : null}
        {attention}
        {office ? <TrendsSection /> : null}
        {progress}
      </div>
    </>
  );
}
