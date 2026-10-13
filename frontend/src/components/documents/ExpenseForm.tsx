"use client";

import { IconFileUpload, IconX } from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { api, upload } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { DOCUMENT_KEYS, useAction, useCategories, useCostCenters, useProjects } from "@/api/queries";
import type { Expense } from "@/api/types";
import { useZone } from "@/components/shell/MeContext";
import { useToast } from "@/components/ui/Toast";
import { Button, ButtonLink } from "@/components/ui/Button";
import { MoneyField, SelectField, TextAreaField, TextField, amountProblem } from "@/components/ui/Field";
import { FormGrid, Panel } from "@/components/ui/Layout";
import { Banner, ErrorState, LoadingBlock } from "@/components/ui/States";
import { PAYMENT_METHODS } from "@/lib/documents";
import { todayInZone } from "@/lib/dates";
import { stripSeparators } from "@/lib/money";
import { AllocationEditor, allocationPayload, newLine, type AllocationLine, type AllocationMethod } from "./AllocationEditor";
import { ReceiptPanel } from "./Panels";
import styles from "./DocumentForm.module.css";

type Kind = "direct" | "indirect";
type Target = "cost_center" | "project";

function initialLines(expense: Expense | undefined): AllocationLine[] {
  if (!expense || expense.allocations.length === 0) return [newLine()];
  return expense.allocations.map((row) => ({
    key: crypto.randomUUID(),
    costCenterId: String(row.cost_center_id),
    value:
      expense.allocation_method === "percentage" && row.basis_points !== null
        ? `${Math.floor(row.basis_points / 100)}.${String(row.basis_points % 100).padStart(2, "0")}`
        : row.amount,
  }));
}

/**
 * Create a draft expense, or change one that is still a draft. Direct expenses go to one cost centre, project or product;
 * indirect ones are split across cost centres. A new expense can be saved with its receipts in one go.
 */
export function ExpenseForm({ initial }: { initial?: Expense }) {
  const router = useRouter();
  const toast = useToast();
  const zone = useZone();
  const categories = useCategories();
  const centres = useCostCenters();
  const projects = useProjects();

  const [kind, setKind] = useState<Kind>(initial?.expense_type ?? "direct");
  const [date, setDate] = useState(initial?.document_date ?? todayInZone(zone));
  const [categoryId, setCategoryId] = useState(initial ? String(initial.category_id) : "");
  const [amount, setAmount] = useState(initial?.amount ?? "");
  const [tax, setTax] = useState(initial && initial.tax_amount !== "0.00" ? initial.tax_amount : "");
  const [method, setMethod] = useState<string>(initial?.payment_method ?? "cash");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [target, setTarget] = useState<Target>(initial?.project_id ? "project" : "cost_center");
  const [centreId, setCentreId] = useState(initial?.cost_center_id ? String(initial.cost_center_id) : "");
  const [projectId, setProjectId] = useState(initial?.project_id ? String(initial.project_id) : "");
  const [splitMethod, setSplitMethod] = useState<AllocationMethod>(initial?.allocation_method ?? "percentage");
  const [lines, setLines] = useState<AllocationLine[]>(() => initialLines(initial));
  const [queued, setQueued] = useState<File[]>([]);
  const files = useRef<HTMLInputElement>(null);

  const save = useAction<{ send: boolean }, { saved: Expense; sendError: unknown }>({
    mutationFn: async ({ send }) => {
      const body: Record<string, unknown> = {
        expense_type: kind,
        document_date: date,
        category_id: Number(categoryId),
        amount: stripSeparators(amount),
        tax_amount: stripSeparators(tax) || "0.00",
        payment_method: method,
        description,
      };
      if (kind === "direct") {
        body.cost_center_id = target === "cost_center" ? Number(centreId) || null : null;
        body.project_id = target === "project" ? Number(projectId) || null : null;
      } else {
        body.allocation = allocationPayload(splitMethod, lines);
      }
      let saved = initial
        ? await api<Expense>(`/expenses/${initial.id}`, { method: "PATCH", body, version: initial.version })
        : await api<Expense>("/expenses", { method: "POST", body });
      if (!initial) {
        for (const file of queued) {
          // A receipt that fails to upload does not undo the saved draft: it can be added again on the next screen.
          await upload(`/expenses/${saved.id}/attachments`, file, () => undefined).catch(() => undefined);
        }
      }
      let sendError: unknown = null;
      if (send) {
        try {
          saved = await api<Expense>(`/expenses/${saved.id}/submit`, { method: "POST", version: saved.version });
        } catch (error) {
          sendError = error;
        }
      }
      return { saved, sendError };
    },
    success: ({ sendError }, { send }) =>
      send && !sendError ? "Expense saved and sent for approval" : initial ? "Expense saved" : "Expense saved as a draft",
    invalidate: DOCUMENT_KEYS,
    onSuccess: ({ saved, sendError }) => {
      router.push(`/expenses/${saved.id}`);
      if (sendError) toast.error(`It was saved as a draft, but could not be sent: ${messageFor(sendError)}`);
    },
  });

  if (categories.isPending || centres.isPending || projects.isPending) return <LoadingBlock label="Loading the form" />;
  const loadError = categories.error ?? centres.error ?? projects.error;
  if (loadError) return <ErrorState error={loadError} onRetry={() => { categories.refetch(); centres.refetch(); projects.refetch(); }} />;

  const error = save.error instanceof ApiError ? save.error : null;
  const problem = (field: string) => error?.fieldMessage(field);
  const amountError = amountProblem(amount) ?? problem("amount");
  const taxError = amountProblem(tax, { allowZero: true }) ?? problem("tax_amount");
  const canSave = categoryId !== "" && amount.trim() !== "" && !amountProblem(amount) && !amountProblem(tax, { allowZero: true });

  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate({ send: false });
      }}
      noValidate
    >
      {error && error.fields.length === 0 ? (
        <Banner tone="negative" title="Could not save">
          {messageFor(error)}
        </Banner>
      ) : null}

      <div className={styles.columns}>
        <div className={styles.main}>
          <Panel title="The expense">
            <FormGrid>
              <div className={`${styles.kind} ${styles.wide}`} role="group" aria-label="Kind of expense">
                <button type="button" aria-pressed={kind === "direct"} onClick={() => setKind("direct")}>
                  <strong>Direct</strong>
                  <span>Charged to one cost centre, project or product</span>
                </button>
                <button type="button" aria-pressed={kind === "indirect"} onClick={() => setKind("indirect")} disabled={initial !== undefined && initial.status !== "draft"}>
                  <strong>Indirect</strong>
                  <span>Shared across several cost centres</span>
                </button>
              </div>
              <TextField label="Date" type="date" value={date} onChange={(event) => setDate(event.target.value)} error={problem("document_date")} required />
              <SelectField
                label="Category"
                value={categoryId}
                onChange={(event) => setCategoryId(event.target.value)}
                options={(categories.data ?? []).map((category) => ({ value: category.id, label: category.name }))}
                placeholder="Choose a category"
                error={problem("category_id")}
                required
              />
              <MoneyField label="Amount" value={amount} onValue={setAmount} error={amountError} hint="The total paid, tax included." required placeholder="0.00" />
              <MoneyField label="Tax included in the amount" value={tax} onValue={setTax} error={taxError} hint="For your records. It is not added on top." placeholder="0.00" />
              <SelectField
                label="Paid by"
                value={method}
                onChange={(event) => setMethod(event.target.value)}
                options={PAYMENT_METHODS.map((option) => ({ value: option.value, label: option.label }))}
                error={problem("payment_method")}
              />
              <TextAreaField
                label="What it was for"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                error={problem("description")}
                hint="Needed before it can be sent for approval."
                className={styles.wide}
              />
            </FormGrid>
          </Panel>

          {kind === "direct" ? (
            <Panel title="Charged to">
              <FormGrid>
                <SelectField
                  label="Charge it to"
                  value={target}
                  onChange={(event) => setTarget(event.target.value as Target)}
                  options={[
                    { value: "cost_center", label: "A cost centre" },
                    { value: "project", label: "A project or product" },
                  ]}
                />
                {target === "cost_center" ? (
                  <SelectField
                    label="Cost centre"
                    value={centreId}
                    onChange={(event) => setCentreId(event.target.value)}
                    options={(centres.data ?? []).map((centre) => ({ value: centre.id, label: `${centre.code} ${centre.name}` }))}
                    placeholder="Choose a cost centre"
                    error={problem("cost_center_id")}
                  />
                ) : (
                  <SelectField
                    label="Project or product"
                    value={projectId}
                    onChange={(event) => setProjectId(event.target.value)}
                    options={(projects.data ?? []).map((project) => ({ value: project.id, label: `${project.code} ${project.name}` }))}
                    placeholder="Choose a project or product"
                    error={problem("project_id")}
                  />
                )}
              </FormGrid>
            </Panel>
          ) : (
            <AllocationEditor
              amount={amount}
              method={splitMethod}
              lines={lines}
              centres={centres.data ?? []}
              onMethod={setSplitMethod}
              onLines={setLines}
              error={problem("allocation") ?? problem("allocation.lines")}
            />
          )}
        </div>

        <div className={styles.side}>
          <Panel title="Receipts">
            {initial ? (
              <ReceiptPanel kind="expenses" id={initial.id} editable />
            ) : (
              <div className={styles.queue}>
                {queued.length === 0 ? <p className="muted">Add the receipt now, or after saving.</p> : null}
                <ul>
                  {queued.map((file, index) => (
                    <li key={`${file.name}-${index}`}>
                      <span className="mono">{file.name}</span>
                      <Button small variant="quiet" icon={<IconX size={14} stroke={1.75} aria-hidden />} onClick={() => setQueued(queued.filter((_, at) => at !== index))} aria-label={`Remove ${file.name}`} />
                    </li>
                  ))}
                </ul>
                <input
                  ref={files}
                  type="file"
                  hidden
                  multiple
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(event) => {
                    setQueued([...queued, ...Array.from(event.target.files ?? [])]);
                    event.target.value = "";
                  }}
                />
                <Button icon={<IconFileUpload size={16} stroke={1.75} aria-hidden />} onClick={() => files.current?.click()}>
                  Choose receipts
                </Button>
              </div>
            )}
          </Panel>
        </div>
      </div>

      <div className={styles.footer}>
        <ButtonLink href={initial ? `/expenses/${initial.id}` : "/expenses"}>Cancel</ButtonLink>
        <Button type="submit" pending={save.isPending && save.variables?.send === false} disabled={!canSave || save.isPending}>
          Save draft
        </Button>
        <Button variant="primary" pending={save.isPending && save.variables?.send === true} disabled={!canSave || save.isPending} onClick={() => save.mutate({ send: true })}>
          Save and send for approval
        </Button>
      </div>
    </form>
  );
}
