"use client";

import { IconCopy, IconPlus, IconScale, IconTrash } from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { DOCUMENT_KEYS, useAccounts, useAction, useCostCenters, useProjects } from "@/api/queries";
import type { Voucher } from "@/api/types";
import { useZone } from "@/components/shell/MeContext";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { SelectField, TextAreaField, TextField } from "@/components/ui/Field";
import { Money } from "@/components/ui/Format";
import { FormGrid, Panel } from "@/components/ui/Layout";
import { Banner, ErrorState, LoadingBlock } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { VOUCHER_TYPES } from "@/lib/documents";
import { todayInZone } from "@/lib/dates";
import { ZERO_PAISA, fromPaisa, isAmount, stripSeparators, subtractAmounts, sumAmounts, toPaisa } from "@/lib/money";
import form from "./DocumentForm.module.css";
import styles from "./VoucherForm.module.css";

interface Line {
  key: string;
  accountId: string;
  description: string;
  centreId: string;
  projectId: string;
  debit: string;
  credit: string;
}

function blank(): Line {
  return { key: crypto.randomUUID(), accountId: "", description: "", centreId: "", projectId: "", debit: "", credit: "" };
}

function positive(text: string): boolean {
  const clean = stripSeparators(text);
  return isAmount(clean) && (toPaisa(clean) ?? ZERO_PAISA) > ZERO_PAISA;
}

/** Why the lines cannot be saved yet, in plain words. An empty list means they can. */
export function voucherProblems(lines: Line[], narration: string): string[] {
  const problems: string[] = [];
  if (lines.length < 2) problems.push("A voucher needs at least two lines.");
  const unfinished = lines.filter((line) => !line.accountId || (positive(line.debit) === positive(line.credit)));
  if (unfinished.length > 0) {
    problems.push(
      `${unfinished.length === 1 ? "One line needs" : `${unfinished.length} lines need`} an account and either a debit or a credit, not both and not neither.`,
    );
  }
  const debit = sumAmounts(lines.map((line) => stripSeparators(line.debit)));
  const credit = sumAmounts(lines.map((line) => stripSeparators(line.credit)));
  if (debit !== credit) problems.push(`Debits and credits differ by ${fromDifference(debit, credit)}. Use the balancing line, or change an amount.`);
  if (!narration.trim()) problems.push("Add a narration saying what the voucher is for.");
  return problems;
}

function fromDifference(debit: string, credit: string): string {
  const paisa = (toPaisa(debit) ?? ZERO_PAISA) - (toPaisa(credit) ?? ZERO_PAISA);
  return fromPaisa(paisa < ZERO_PAISA ? -paisa : paisa).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Create a draft voucher, or change one that is still a draft. Lines are typed like a spreadsheet: Tab moves across, Enter
 * in an amount goes to the next line, and a new line opens after the last. The strip at the bottom always shows debits,
 * credits and the difference, and one button adds the exact line that balances them.
 */
export function VoucherForm({ initial, onClose }: { initial?: Voucher; onClose?: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const zone = useZone();
  const accounts = useAccounts();
  const centres = useCostCenters();
  const projects = useProjects();

  const [type, setType] = useState<string>(initial?.voucher_type ?? "PV");
  const [date, setDate] = useState(initial?.document_date ?? todayInZone(zone));
  const [narration, setNarration] = useState(initial?.description ?? "");
  const [lines, setLines] = useState<Line[]>(() =>
    initial
      ? initial.lines.map((line) => ({
          key: crypto.randomUUID(),
          accountId: String(line.account_id),
          description: line.description ?? "",
          centreId: line.cost_center_id ? String(line.cost_center_id) : "",
          projectId: line.project_id ? String(line.project_id) : "",
          debit: line.debit === "0.00" ? "" : line.debit,
          credit: line.credit === "0.00" ? "" : line.credit,
        }))
      : [blank(), blank()],
  );
  const accountRefs = useRef(new Map<string, HTMLButtonElement>());
  // A line added by a key press or a button is focused once it has been drawn.
  const focusAfterDraw = useRef<string | null>(null);
  useEffect(() => {
    if (focusAfterDraw.current) {
      accountRefs.current.get(focusAfterDraw.current)?.focus();
      focusAfterDraw.current = null;
    }
  });

  const postable = useMemo(() => (accounts.data ?? []).filter((account) => account.is_postable), [accounts.data]);
  const debitTotal = sumAmounts(lines.map((line) => stripSeparators(line.debit)));
  const creditTotal = sumAmounts(lines.map((line) => stripSeparators(line.credit)));
  const difference = subtractAmounts(debitTotal, creditTotal);
  const balanced = difference === "0.00";
  const problems = voucherProblems(lines, narration);

  const save = useAction<{ send: boolean }, { saved: Voucher; sendError: unknown }>({
    mutationFn: async ({ send }) => {
      const body = {
        voucher_type: type,
        document_date: date,
        description: narration,
        lines: lines.map((line) => ({
          account_id: Number(line.accountId),
          debit: stripSeparators(line.debit) || "0.00",
          credit: stripSeparators(line.credit) || "0.00",
          description: line.description.trim() || null,
          cost_center_id: line.centreId ? Number(line.centreId) : null,
          project_id: line.projectId ? Number(line.projectId) : null,
        })),
      };
      const patch = initial ? { document_date: body.document_date, description: body.description, lines: body.lines } : null;
      let saved = initial
        ? await api<Voucher>(`/vouchers/${initial.id}`, { method: "PATCH", body: patch, version: initial.version })
        : await api<Voucher>("/vouchers", { method: "POST", body });
      let sendError: unknown = null;
      if (send) {
        try {
          saved = await api<Voucher>(`/vouchers/${saved.id}/submit`, { method: "POST", version: saved.version });
        } catch (error) {
          sendError = error;
        }
      }
      return { saved, sendError };
    },
    success: ({ sendError }, { send }) => (send && !sendError ? "Voucher saved and sent for approval" : "Voucher saved as a draft"),
    invalidate: DOCUMENT_KEYS,
    onSuccess: ({ saved, sendError }) => {
      onClose?.();
      router.push(`/vouchers/${saved.id}`);
      if (sendError) toast.error(`It was saved as a draft, but could not be sent: ${messageFor(sendError)}`);
    },
  });

  if (accounts.isPending || centres.isPending || projects.isPending) return <LoadingBlock shape="form" label="Loading the form" />;
  const loadError = accounts.error ?? centres.error ?? projects.error;
  if (loadError) return <ErrorState error={loadError} onRetry={() => { accounts.refetch(); centres.refetch(); projects.refetch(); }} />;

  const error = save.error instanceof ApiError ? save.error : null;

  function change(key: string, patch: Partial<Line>) {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  }

  /** Typing in one side empties the other: a line has a debit or a credit, never both. */
  function setSide(key: string, side: "debit" | "credit", value: string) {
    const other = value.trim() ? { [side === "debit" ? "credit" : "debit"]: "" } : {};
    change(key, { [side]: value, ...other });
  }

  function addLine(after?: string): string {
    const line = blank();
    setLines((current) => {
      if (!after) return [...current, line];
      const at = current.findIndex((other) => other.key === after);
      return [...current.slice(0, at + 1), line, ...current.slice(at + 1)];
    });
    return line.key;
  }

  function addBalancing() {
    const paisa = toPaisa(difference) ?? ZERO_PAISA;
    if (paisa === ZERO_PAISA) return;
    const line = blank();
    // More debit than credit needs a credit to match, and the other way round.
    if (paisa > ZERO_PAISA) line.credit = difference;
    else line.debit = fromPaisa(-paisa);
    const empty = lines.findIndex((other) => !other.accountId && !other.debit && !other.credit);
    if (empty >= 0 && lines.length > 2) {
      setLines(lines.map((other, index) => (index === empty ? { ...line, key: other.key } : other)));
      focusAfterDraw.current = lines[empty].key;
    } else {
      setLines([...lines, line]);
      focusAfterDraw.current = line.key;
    }
  }

  function onAmountKey(event: React.KeyboardEvent, index: number) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const next = lines[index + 1];
    if (next) accountRefs.current.get(next.key)?.focus();
    else focusAfterDraw.current = addLine();
  }

  const canSave = problems.length === 0;

  return (
    <form
      className={form.form}
      onSubmit={(event) => {
        event.preventDefault();
        if (canSave) save.mutate({ send: false });
      }}
      noValidate
    >
      {error && error.fields.length === 0 ? (
        <Banner tone="negative" title="Could not save">
          {messageFor(error)}
        </Banner>
      ) : null}

      <Panel title="The voucher">
        <FormGrid columns={3}>
          <SelectField label="Type" value={type} onChange={(event) => setType(event.target.value)} options={VOUCHER_TYPES.map((option) => ({ value: option.value, label: option.label }))} disabled={initial !== undefined} hint={initial ? "A voucher keeps its type." : undefined} />
          <TextField label="Date" type="date" value={date} onChange={(event) => setDate(event.target.value)} error={error?.fieldMessage("document_date")} required />
          <div />
          <TextAreaField label="Narration" value={narration} onChange={(event) => setNarration(event.target.value)} hint="What the voucher is for. Needed before it can be sent." className={form.wide} rows={2} required />
        </FormGrid>
      </Panel>

      <Panel title="Lines" flush>
        <div className={styles.scroll}>
          <table className={styles.grid}>
            <caption className="sr-only">Voucher lines. Tab moves across a line; Enter in an amount moves to the next line.</caption>
            <thead>
              <tr>
                <th scope="col" className={styles.no}>#</th>
                <th scope="col">Account</th>
                <th scope="col">Line note</th>
                <th scope="col">Cost centre</th>
                <th scope="col">Project</th>
                <th scope="col" className={`num ${styles.debitHead}`}>Debit</th>
                <th scope="col" className={`num ${styles.creditHead}`}>Credit</th>
                <th scope="col"><span className="sr-only">Line actions</span></th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={line.key}>
                  <td className={styles.no}>{index + 1}</td>
                  <td>
                    <Select
                      variant="cell"
                      ref={(element) => {
                        if (element) accountRefs.current.set(line.key, element);
                        else accountRefs.current.delete(line.key);
                      }}
                      aria-label={`Account, line ${index + 1}`}
                      value={line.accountId}
                      placeholder="Choose an account"
                      options={postable.map((account) => ({ value: account.id, label: `${account.code} ${account.name}` }))}
                      onChange={(next) => change(line.key, { accountId: next })}
                    />
                  </td>
                  <td>
                    <input className={`${styles.cell} user-text`} aria-label={`Note, line ${index + 1}`} value={line.description} onChange={(event) => change(line.key, { description: event.target.value })} />
                  </td>
                  <td>
                    <Select variant="cell" aria-label={`Cost centre, line ${index + 1}`} value={line.centreId} placeholder="None" options={(centres.data ?? []).map((centre) => ({ value: centre.id, label: centre.code }))} onChange={(next) => change(line.key, { centreId: next })} />
                  </td>
                  <td>
                    <Select variant="cell" aria-label={`Project, line ${index + 1}`} value={line.projectId} placeholder="None" options={(projects.data ?? []).map((project) => ({ value: project.id, label: project.code }))} onChange={(next) => change(line.key, { projectId: next })} />
                  </td>
                  <td className={styles.debitCell}>
                    <input
                      className={`${styles.cell} ${styles.amount} num`}
                      aria-label={`Debit, line ${index + 1}`}
                      inputMode="decimal"
                      autoComplete="off"
                      value={line.debit}
                      placeholder="0.00"
                      onChange={(event) => setSide(line.key, "debit", event.target.value)}
                      onKeyDown={(event) => onAmountKey(event, index)}
                    />
                  </td>
                  <td className={styles.creditCell}>
                    <input
                      className={`${styles.cell} ${styles.amount} num`}
                      aria-label={`Credit, line ${index + 1}`}
                      inputMode="decimal"
                      autoComplete="off"
                      value={line.credit}
                      placeholder="0.00"
                      onChange={(event) => setSide(line.key, "credit", event.target.value)}
                      onKeyDown={(event) => onAmountKey(event, index)}
                    />
                  </td>
                  <td className={styles.tools}>
                    <Button variant="quiet" small icon={<IconCopy size={15} stroke={1.75} aria-hidden />} aria-label={`Copy line ${index + 1}`} onClick={() => { const key = addLine(line.key); change(key, { ...line, key }); }} />
                    <Button variant="quiet" small icon={<IconTrash size={15} stroke={1.75} aria-hidden />} aria-label={`Remove line ${index + 1}`} disabled={lines.length <= 2} onClick={() => setLines(lines.filter((other) => other.key !== line.key))} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className={styles.addRow}>
          <Button small icon={<IconPlus size={16} stroke={1.75} aria-hidden />} onClick={() => { focusAfterDraw.current = addLine(); }}>
            Add a line
          </Button>
          {error?.fieldMessage("lines") ? <span className={styles.error} role="alert">{error.fieldMessage("lines")}</span> : null}
        </div>
      </Panel>

      <div className={styles.footer}>
        <div className={`${styles.strip} ${balanced ? styles.ok : styles.off}`} role="status" aria-live="polite">
          <dl>
            <div><dt>Debit</dt><dd><Money currency value={debitTotal} strong /></dd></div>
            <div><dt>Credit</dt><dd><Money currency value={creditTotal} strong /></dd></div>
            <div><dt>Difference</dt><dd><Money currency value={difference.replace("-", "")} strong /></dd></div>
          </dl>
          <p className={styles.state}>{balanced ? (lines.length >= 2 ? "Balanced" : "Add lines") : `${(toPaisa(difference) ?? ZERO_PAISA) > ZERO_PAISA ? "Debits are higher" : "Credits are higher"}`}</p>
          <Button icon={<IconScale size={18} stroke={1.75} aria-hidden />} onClick={addBalancing} disabled={balanced}>
            Add the balancing line
          </Button>
        </div>
        <div className={styles.actions}>
          {problems.length > 0 ? (
            <div className={styles.why} id="why-not">
              <p className={styles.whyTitle}>It cannot be saved yet</p>
              <ul>
                {problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="muted">Ready to save.</p>
          )}
          <div className={styles.buttons}>
            {onClose ? <Button onClick={onClose}>Cancel</Button> : <ButtonLink href={initial ? `/vouchers/${initial.id}` : "/vouchers"}>Cancel</ButtonLink>}
            <Button type="submit" pending={save.isPending && save.variables?.send === false} disabled={!canSave || save.isPending} aria-describedby={problems.length > 0 ? "why-not" : undefined}>
              Save draft
            </Button>
            <Button variant="primary" pending={save.isPending && save.variables?.send === true} disabled={!canSave || save.isPending} onClick={() => save.mutate({ send: true })} aria-describedby={problems.length > 0 ? "why-not" : undefined}>
              Save and send for approval
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}
