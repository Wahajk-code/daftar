"use client";

import { IconPlus, IconTrash } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "@/api/client";
import type { AllocationPreview, CostCenter } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { MoneyField, SelectField, TextField, amountProblem } from "@/components/ui/Field";
import { Money } from "@/components/ui/Format";
import { isAmount, stripSeparators, toPaisa } from "@/lib/money";
import { useDebounced } from "@/lib/use-debounced";
import styles from "./AllocationEditor.module.css";

export type AllocationMethod = "percentage" | "fixed";

export interface AllocationLine {
  key: string;
  costCenterId: string;
  /** Percentage text ("33.33") or amount text ("1500.00"), as typed. */
  value: string;
}

export function newLine(): AllocationLine {
  return { key: crypto.randomUUID(), costCenterId: "", value: "" };
}

/** What the API takes: basis points for a percentage split, an amount for a fixed one. Null while a line is unfinished. */
export function allocationPayload(method: AllocationMethod, lines: AllocationLine[]) {
  const payload = lines.map((line) => {
    const cost_center_id = Number(line.costCenterId);
    const clean = stripSeparators(line.value);
    if (!line.costCenterId || !isAmount(clean)) return null;
    if (method === "percentage") return { cost_center_id, basis_points: Number(toPaisa(clean)) };
    return { cost_center_id, amount: clean };
  });
  return payload.every((line) => line !== null) && payload.length > 0 ? { method, lines: payload as NonNullable<(typeof payload)[number]>[] } : null;
}

/** Splits 100% as evenly as whole basis points allow, the odd ones going to the first lines. */
export function shareEqually(count: number): string[] {
  if (count === 0) return [];
  const base = Math.floor(10000 / count);
  const extra = 10000 % count;
  return Array.from({ length: count }, (_, index) => {
    const bp = base + (index < extra ? 1 : 0);
    return `${Math.floor(bp / 100)}.${String(bp % 100).padStart(2, "0")}`;
  });
}

/**
 * The split of an indirect expense across cost centres. As lines are typed, the server works out what each centre would get
 * (largest remainder, so the parts always add up) and how much is still unallocated; nothing is calculated here.
 */
export function AllocationEditor({
  amount,
  method,
  lines,
  centres,
  onMethod,
  onLines,
  error,
}: {
  amount: string;
  method: AllocationMethod;
  lines: AllocationLine[];
  centres: CostCenter[];
  onMethod: (method: AllocationMethod) => void;
  onLines: (lines: AllocationLine[]) => void;
  error?: string;
}) {
  const payload = useMemo(() => allocationPayload(method, lines), [method, lines]);
  const cleanAmount = stripSeparators(amount);
  const ready = payload !== null && isAmount(cleanAmount) && !amountProblem(cleanAmount);
  const settled = useDebounced(ready ? JSON.stringify({ amount: cleanAmount, allocation: payload }) : "", 300);

  const preview = useQuery({
    queryKey: ["allocation-preview", settled],
    queryFn: () => api<AllocationPreview>("/expenses/preview-allocation", { method: "POST", body: JSON.parse(settled) }),
    enabled: settled !== "",
    placeholderData: (previous) => previous,
  });

  const used = new Set(lines.map((line) => line.costCenterId).filter(Boolean));
  const options = (current: string) =>
    centres.filter((centre) => centre.id === Number(current) || !used.has(String(centre.id))).map((centre) => ({ value: centre.id, label: `${centre.code} ${centre.name}` }));

  function change(key: string, patch: Partial<AllocationLine>) {
    onLines(lines.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  }

  const data = settled !== "" ? preview.data : undefined;

  return (
    <fieldset className={styles.editor}>
      <legend>Split across cost centres</legend>
      <div className={styles.method} role="group" aria-label="How to split">
        <button type="button" aria-pressed={method === "percentage"} onClick={() => onMethod("percentage")}>
          By percentage
        </button>
        <button type="button" aria-pressed={method === "fixed"} onClick={() => onMethod("fixed")}>
          By amount
        </button>
      </div>

      <div className={styles.rows}>
        {lines.map((line, index) => (
          <div key={line.key} className={styles.row}>
            <SelectField
              label={`Cost centre ${index + 1}`}
              hideLabel
              placeholder="Choose a cost centre"
              options={options(line.costCenterId)}
              value={line.costCenterId}
              onChange={(event) => change(line.key, { costCenterId: event.target.value })}
            />
            {method === "percentage" ? (
              <TextField
                label={`Percentage ${index + 1}`}
                hideLabel
                inputMode="decimal"
                placeholder="Percent, such as 33.33"
                value={line.value}
                onChange={(event) => change(line.key, { value: event.target.value })}
                className={styles.value}
              />
            ) : (
              <MoneyField
                label={`Amount ${index + 1}`}
                hideLabel
                placeholder="Amount"
                value={line.value}
                onValue={(value) => change(line.key, { value })}
                className={styles.value}
              />
            )}
            <Button variant="quiet" icon={<IconTrash size={18} stroke={1.75} aria-hidden />} onClick={() => onLines(lines.filter((other) => other.key !== line.key))} aria-label={`Remove line ${index + 1}`} disabled={lines.length === 1} />
          </div>
        ))}
      </div>

      <div className={styles.tools}>
        <Button small icon={<IconPlus size={16} stroke={1.75} aria-hidden />} onClick={() => onLines([...lines, newLine()])} disabled={lines.length >= centres.length}>
          Add a cost centre
        </Button>
        {method === "percentage" && lines.length > 1 ? (
          <Button
            small
            variant="quiet"
            onClick={() => {
              const shares = shareEqually(lines.length);
              onLines(lines.map((line, index) => ({ ...line, value: shares[index] ?? "" })));
            }}
          >
            Share equally
          </Button>
        ) : null}
      </div>

      <div className={`${styles.strip} ${data?.complete ? styles.ok : data ? styles.off : ""}`} aria-live="polite">
        {data ? (
          <>
            <span>
              Allocated <Money value={data.allocated} /> of <Money value={cleanAmount} />
            </span>
            <span>
              {data.complete ? "The split is exact." : (
                <>
                  Still to allocate <Money value={data.remaining} />
                  {data.remaining_basis_points ? ` (${data.remaining_basis_points / 100}%)` : ""}
                </>
              )}
            </span>
          </>
        ) : (
          <span className="muted">Enter the amount and choose the cost centres to see how it splits.</span>
        )}
      </div>

      {data && data.lines.length > 0 ? (
        <table className={styles.preview}>
          <caption className="sr-only">What each cost centre is charged</caption>
          <thead>
            <tr>
              <th scope="col">Cost centre</th>
              <th scope="col" className="num">Share</th>
              <th scope="col" className="num">Charged</th>
            </tr>
          </thead>
          <tbody>
            {data.lines.map((line) => (
              <tr key={line.cost_center_id}>
                <td>{line.cost_center_code}</td>
                <td className="num">{line.basis_points === null ? "" : `${line.basis_points / 100}%`}</td>
                <td className="num"><Money value={line.amount} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
    </fieldset>
  );
}
