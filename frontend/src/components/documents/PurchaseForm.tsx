"use client";

import { IconFileUpload, IconPlus, IconTrash, IconX } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { api, upload } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { DOCUMENT_KEYS, useAction, useVendors } from "@/api/queries";
import type { Purchase, PurchasePreview } from "@/api/types";
import { useZone } from "@/components/shell/MeContext";
import { Button, ButtonLink } from "@/components/ui/Button";
import { MoneyField, SelectField, TextAreaField, TextField, amountProblem } from "@/components/ui/Field";
import { Money } from "@/components/ui/Format";
import { FormGrid, Panel } from "@/components/ui/Layout";
import { Banner, ErrorState, LoadingBlock } from "@/components/ui/States";
import { Tag } from "@/components/ui/Stamp";
import { useToast } from "@/components/ui/Toast";
import { todayInZone } from "@/lib/dates";
import { bpToPercent, formatBasisPoints, isAmount, percentToBp, stripSeparators, sumAmounts, toPaisa } from "@/lib/money";
import { useDebounced } from "@/lib/use-debounced";
import { ReceiptPanel } from "./Panels";
import form from "./DocumentForm.module.css";
import styles from "./PurchaseForm.module.css";

interface Line {
  key: string;
  item: string;
  category: "goods" | "services" | "contracts";
  quantity: string;
  rate: string;
  /** Sales tax as a percentage, as typed ("18"). */
  tax: string;
}

const QUANTITY = /^\d{1,9}(\.\d{1,3})?$/;

function blankLine(): Line {
  return { key: crypto.randomUUID(), item: "", category: "goods", quantity: "1", rate: "", tax: "0" };
}

function payloadLines(lines: Line[]) {
  const out = lines.map((line) => {
    const bp = percentToBp(line.tax);
    const rate = stripSeparators(line.rate);
    if (!line.item.trim() || !QUANTITY.test(line.quantity.trim()) || Number(line.quantity) === 0 || !isAmount(rate) || toPaisa(rate) === BigInt(0) || bp === null) return null;
    return { item: line.item.trim(), category: line.category, quantity: line.quantity.trim(), rate, sales_tax_bp: bp };
  });
  return out.every((line) => line !== null) && out.length > 0 ? (out as NonNullable<(typeof out)[number]>[]) : null;
}

export function PurchaseForm({ initial }: { initial?: Purchase }) {
  const router = useRouter();
  const toast = useToast();
  const zone = useZone();
  const vendors = useVendors();

  const [vendorId, setVendorId] = useState(initial ? String(initial.vendor_id) : "");
  const [date, setDate] = useState(initial?.document_date ?? todayInZone(zone));
  const [invoice, setInvoice] = useState(initial?.invoice_number ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [lines, setLines] = useState<Line[]>(() =>
    initial
      ? initial.lines.map((line) => ({
          key: crypto.randomUUID(),
          item: line.item,
          category: line.category as Line["category"],
          quantity: line.quantity,
          rate: line.rate,
          tax: bpToPercent(line.sales_tax_bp),
        }))
      : [blankLine()],
  );
  const [queued, setQueued] = useState<File[]>([]);
  const files = useRef<HTMLInputElement>(null);

  const vendor = vendors.data?.find((row) => row.id === Number(vendorId));
  const payload = useMemo(() => payloadLines(lines), [lines]);
  const settled = useDebounced(vendorId !== "" && payload ? JSON.stringify({ vendor_id: Number(vendorId), document_date: date, lines: payload }) : "", 300);
  const preview = useQuery({
    queryKey: ["purchase-preview", settled],
    queryFn: () => api<PurchasePreview>("/purchases/preview", { method: "POST", body: JSON.parse(settled) }),
    enabled: settled !== "",
    placeholderData: (previous) => previous,
    retry: false,
  });
  const priced = settled !== "" ? preview.data : undefined;

  const save = useAction<{ send: boolean }, { saved: Purchase; sendError: unknown }>({
    mutationFn: async ({ send }) => {
      const body = { vendor_id: Number(vendorId), document_date: date, invoice_number: invoice.trim() || null, description, lines: payload };
      let saved = initial
        ? await api<Purchase>(`/purchases/${initial.id}`, { method: "PATCH", body, version: initial.version })
        : await api<Purchase>("/purchases", { method: "POST", body });
      if (!initial) {
        for (const file of queued) await upload(`/purchases/${saved.id}/attachments`, file, () => undefined).catch(() => undefined);
      }
      let sendError: unknown = null;
      if (send) {
        try {
          saved = await api<Purchase>(`/purchases/${saved.id}/submit`, { method: "POST", version: saved.version });
        } catch (error) {
          sendError = error;
        }
      }
      return { saved, sendError };
    },
    success: ({ sendError }, { send }) => (send && !sendError ? "Purchase saved and sent for approval" : initial ? "Purchase saved" : "Purchase saved as a draft"),
    invalidate: DOCUMENT_KEYS,
    onSuccess: ({ saved, sendError }) => {
      router.push(`/purchases/${saved.id}`);
      if (sendError) toast.error(`It was saved as a draft, but could not be sent: ${messageFor(sendError)}`);
    },
  });

  if (vendors.isPending) return <LoadingBlock label="Loading the form" />;
  if (vendors.error) return <ErrorState error={vendors.error} onRetry={() => vendors.refetch()} />;

  const error = save.error instanceof ApiError ? save.error : null;
  const problem = (field: string) => error?.fieldMessage(field);
  const previewError = preview.error instanceof ApiError && settled !== "" ? preview.error : null;
  const canSave = vendorId !== "" && payload !== null;
  const needsInvoice = vendor?.is_sales_tax_registered === true;

  function change(key: string, patch: Partial<Line>) {
    setLines(lines.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  }

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

      <div className={form.columns}>
        <div className={form.main}>
          <Panel title="The purchase">
            <FormGrid>
              <SelectField
                label="Vendor"
                value={vendorId}
                onChange={(event) => setVendorId(event.target.value)}
                options={(vendors.data ?? []).map((row) => ({ value: row.id, label: row.name }))}
                placeholder="Choose a vendor"
                error={problem("vendor_id")}
                required
              />
              <TextField label="Date" type="date" value={date} onChange={(event) => setDate(event.target.value)} error={problem("document_date")} required />
              <TextField
                label="Invoice number"
                value={invoice}
                onChange={(event) => setInvoice(event.target.value)}
                error={problem("invoice_number")}
                hint={needsInvoice ? "Required: this vendor is registered for sales tax." : "Not needed for a vendor without sales tax registration."}
                required={needsInvoice}
              />
              {vendor ? (
                <div className={styles.vendorTags} aria-label="About the vendor">
                  <Tag tone={vendor.is_sales_tax_registered ? "positive" : "caution"}>{vendor.is_sales_tax_registered ? "Registered" : "Not registered"}</Tag>
                  <Tag tone={vendor.is_filer ? "positive" : "caution"}>{vendor.is_filer ? "Filer" : "Non-filer"}</Tag>
                </div>
              ) : null}
              <TextAreaField label="What it was for" value={description} onChange={(event) => setDescription(event.target.value)} error={problem("description")} className={form.wide} />
            </FormGrid>
            {vendor && !vendor.is_sales_tax_registered ? (
              <div className={styles.memo}>
                <Banner tone="info" title="This will be a purchase memo">
                  The vendor is not registered for sales tax, so there is no tax invoice. Tax is withheld on the gross value, and the memo
                  is marked as such in the records.
                </Banner>
              </div>
            ) : null}
          </Panel>

          <Panel title="Lines" flush>
            <div className={styles.scroll}>
              <table className={styles.grid}>
                <caption className="sr-only">Purchase lines, with the tax worked out for each</caption>
                <thead>
                  <tr>
                    <th scope="col">Item</th>
                    <th scope="col">Kind</th>
                    <th scope="col" className="num">Quantity</th>
                    <th scope="col" className="num">Rate</th>
                    <th scope="col" className="num">Sales tax %</th>
                    <th scope="col" className={`num ${styles.worked}`}>Subtotal</th>
                    <th scope="col" className={`num ${styles.worked}`}>Sales tax</th>
                    <th scope="col" className={`num ${styles.worked}`}>Withheld</th>
                    <th scope="col" className={`num ${styles.worked}`}>Payable</th>
                    <th scope="col"><span className="sr-only">Remove</span></th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line, index) => {
                    const worked = priced?.lines[index];
                    return (
                      <tr key={line.key}>
                        <td>
                          <TextField label={`Item ${index + 1}`} hideLabel value={line.item} onChange={(event) => change(line.key, { item: event.target.value })} placeholder="What was bought" />
                        </td>
                        <td>
                          <SelectField
                            label={`Kind ${index + 1}`}
                            hideLabel
                            value={line.category}
                            onChange={(event) => change(line.key, { category: event.target.value as Line["category"] })}
                            options={[
                              { value: "goods", label: "Goods" },
                              { value: "services", label: "Services" },
                              { value: "contracts", label: "Contracts" },
                            ]}
                          />
                        </td>
                        <td>
                          <TextField label={`Quantity ${index + 1}`} hideLabel inputMode="decimal" value={line.quantity} onChange={(event) => change(line.key, { quantity: event.target.value })} className={styles.right} />
                        </td>
                        <td>
                          <MoneyField label={`Rate ${index + 1}`} hideLabel value={line.rate} onValue={(rate) => change(line.key, { rate })} placeholder="0.00" error={amountProblem(line.rate)} />
                        </td>
                        <td>
                          <TextField label={`Sales tax percent ${index + 1}`} hideLabel inputMode="decimal" value={line.tax} onChange={(event) => change(line.key, { tax: event.target.value })} className={styles.right} />
                        </td>
                        <td className={`num ${styles.worked}`}>{worked ? <Money value={worked.subtotal} /> : ""}</td>
                        <td className={`num ${styles.worked}`}>{worked ? <Money value={worked.sales_tax} /> : ""}</td>
                        <td className={`num ${styles.worked}`}>
                          {worked ? (
                            <span title={`Sales tax ${formatBasisPoints(worked.sales_withholding_bp)}, income tax ${formatBasisPoints(worked.income_withholding_bp)}`}>
                              <Money value={sumAmounts([worked.sales_tax_withheld, worked.income_tax_withheld])} />
                            </span>
                          ) : (
                            ""
                          )}
                        </td>
                        <td className={`num ${styles.worked}`}>{worked ? <Money value={worked.payable} strong /> : ""}</td>
                        <td>
                          <Button variant="quiet" icon={<IconTrash size={16} stroke={1.75} aria-hidden />} onClick={() => setLines(lines.filter((other) => other.key !== line.key))} disabled={lines.length === 1} aria-label={`Remove line ${index + 1}`} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                {priced ? (
                  <tfoot>
                    <tr>
                      <th scope="row" colSpan={5}>Totals</th>
                      <td className="num"><Money value={priced.totals.subtotal} /></td>
                      <td className="num"><Money value={priced.totals.sales_tax_total} /></td>
                      <td className="num"><Money value={sumAmounts([priced.totals.sales_tax_withheld, priced.totals.income_tax_withheld])} /></td>
                      <td className="num"><Money value={priced.totals.payable} strong /></td>
                      <td />
                    </tr>
                  </tfoot>
                ) : null}
              </table>
            </div>
            <div className={styles.lineTools}>
              <Button small icon={<IconPlus size={14} stroke={1.75} aria-hidden />} onClick={() => setLines([...lines, blankLine()])}>
                Add a line
              </Button>
              {problem("lines") ? <span className={styles.error} role="alert">{problem("lines")}</span> : null}
            </div>
          </Panel>

          {previewError ? (
            <Banner tone="caution" title="The tax could not be worked out">
              {messageFor(previewError)}
            </Banner>
          ) : null}
          {priced ? (
            <Panel title="What is owed">
              <dl className={styles.totals}>
                <div><dt>Subtotal</dt><dd><Money value={priced.totals.subtotal} /></dd></div>
                <div><dt>Sales tax charged</dt><dd><Money value={priced.totals.sales_tax_total} /></dd></div>
                <div><dt>Gross value</dt><dd><Money value={priced.totals.gross_total} /></dd></div>
                <div><dt>Sales tax withheld</dt><dd><Money value={priced.totals.sales_tax_withheld} /></dd></div>
                <div><dt>Income tax withheld</dt><dd><Money value={priced.totals.income_tax_withheld} /></dd></div>
                <div className={styles.payable}><dt>Payable to the vendor</dt><dd><Money value={priced.totals.payable} strong /></dd></div>
              </dl>
              <p className="faint">The withholding rates in force on the date of the purchase are read from the Tax rates screen and kept on the purchase.</p>
            </Panel>
          ) : null}
        </div>

        <div className={form.side}>
          <Panel title="Receipts">
            {initial ? (
              <ReceiptPanel kind="purchases" id={initial.id} editable />
            ) : (
              <div className={form.queue}>
                {queued.length === 0 ? <p className="muted">Add the invoice or memo now, or after saving.</p> : null}
                <ul>
                  {queued.map((file, index) => (
                    <li key={`${file.name}-${index}`}>
                      <span className="mono">{file.name}</span>
                      <Button small variant="quiet" icon={<IconX size={14} stroke={1.75} aria-hidden />} onClick={() => setQueued(queued.filter((_, at) => at !== index))} aria-label={`Remove ${file.name}`} />
                    </li>
                  ))}
                </ul>
                <input ref={files} type="file" hidden multiple accept="image/jpeg,image/png,image/webp" onChange={(event) => { setQueued([...queued, ...Array.from(event.target.files ?? [])]); event.target.value = ""; }} />
                <Button icon={<IconFileUpload size={16} stroke={1.75} aria-hidden />} onClick={() => files.current?.click()}>
                  Choose files
                </Button>
              </div>
            )}
          </Panel>
        </div>
      </div>

      <div className={form.footer}>
        <ButtonLink href={initial ? `/purchases/${initial.id}` : "/purchases"}>Cancel</ButtonLink>
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
