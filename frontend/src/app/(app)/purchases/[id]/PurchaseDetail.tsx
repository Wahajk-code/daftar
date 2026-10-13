"use client";

import { IconFilePlus, IconPencil } from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/api/client";
import { DOCUMENT_KEYS, useAction, useCategories, useRecord } from "@/api/queries";
import type { Purchase, Voucher } from "@/api/types";
import { DocumentActions } from "@/components/documents/DocumentActions";
import { DuplicatePanel, HistoryPanel, ReceiptPanel } from "@/components/documents/Panels";
import { useMe } from "@/components/shell/MeContext";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { SelectField } from "@/components/ui/Field";
import { DateText, Identifier, Instant, Money } from "@/components/ui/Format";
import { Facts, PageHeader, Panel } from "@/components/ui/Layout";
import { ErrorState, LoadingBlock } from "@/components/ui/States";
import { Stamp, Tag } from "@/components/ui/Stamp";
import { PAYMENT_METHODS } from "@/lib/documents";
import { formatBasisPoints } from "@/lib/money";
import view from "@/components/documents/DocumentView.module.css";

const KIND_TEXT: Record<string, string> = { goods: "Goods", services: "Services", contracts: "Contracts", any: "Any" };

function GenerateDialog({ purchase, open, onClose }: { purchase: Purchase; open: boolean; onClose: () => void }) {
  const router = useRouter();
  const categories = useCategories();
  const [categoryId, setCategoryId] = useState("");
  const [method, setMethod] = useState("bank_transfer");
  const generate = useAction<void, Voucher>({
    mutationFn: () => api<Voucher>(`/purchases/${purchase.id}/generate-voucher`, { method: "POST", body: { category_id: Number(categoryId), payment_method: method } }),
    success: "Voucher created",
    invalidate: DOCUMENT_KEYS,
    onSuccess: (voucher) => router.push(`/vouchers/${voucher.id}`),
  });
  return (
    <Dialog open={open} onClose={onClose} title="Generate the payment voucher">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          generate.mutate();
        }}
        style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
      >
        <p>The voucher debits the expense account of the category and the input tax, and credits what is paid and each tax withheld.</p>
        <SelectField
          label="Expense category"
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
          options={(categories.data ?? []).map((category) => ({ value: category.id, label: category.name }))}
          placeholder="Choose a category"
          required
        />
        <SelectField label="Paid by" value={method} onChange={(event) => setMethod(event.target.value)} options={PAYMENT_METHODS.map((option) => ({ value: option.value, label: option.label }))} />
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
          <Button onClick={onClose} disabled={generate.isPending}>Cancel</Button>
          <Button type="submit" variant="primary" pending={generate.isPending} disabled={categoryId === ""}>Generate voucher</Button>
        </div>
      </form>
    </Dialog>
  );
}

export function PurchaseDetail({ id }: { id: number }) {
  const me = useMe();
  const purchase = useRecord<Purchase>(["purchases", id], `/purchases/${id}`);
  const [generating, setGenerating] = useState(false);

  if (purchase.isPending) return <LoadingBlock label="Loading the purchase" />;
  if (purchase.error) return <ErrorState error={purchase.error} onRetry={() => purchase.refetch()} />;
  const doc = purchase.data;
  const editable = doc.created_by === me.id && doc.status === "draft";
  const canGenerate = (me.role === "admin" || me.role === "accountant") && doc.status === "approved" && !doc.voucher;

  return (
    <>
      <PageHeader
        back={{ href: "/purchases", label: "Purchases" }}
        title={<span className="user-text">{doc.vendor_name}</span>}
        meta={
          <>
            <Stamp status={doc.status} />
            {doc.invoice_number ? <Identifier value={doc.invoice_number} /> : <Tag>Purchase memo</Tag>}
            <span className="muted">Purchase {doc.id}</span>
          </>
        }
        actions={
          editable ? (
            <ButtonLink href={`/purchases/${id}/edit`} icon={<IconPencil size={16} stroke={1.75} aria-hidden />}>
              Edit
            </ButtonLink>
          ) : undefined
        }
      />
      <div className={view.layout}>
        <div className={view.main}>
          <DuplicatePanel kind="purchases" id={id} />
          <DocumentActions kind="purchases" doc={doc}>
            {canGenerate ? (
              <Button variant="primary" icon={<IconFilePlus size={16} stroke={1.75} aria-hidden />} onClick={() => setGenerating(true)}>
                Generate payment voucher
              </Button>
            ) : null}
          </DocumentActions>

          <Panel title="Lines" flush>
            <div style={{ overflowX: "auto" }}>
              <table className={view.split} style={{ minWidth: 880 }}>
                <caption className="sr-only">Purchase lines with the tax on each</caption>
                <thead>
                  <tr>
                    <th scope="col">Item</th>
                    <th scope="col">Kind</th>
                    <th scope="col" className="num">Quantity</th>
                    <th scope="col" className="num">Rate</th>
                    <th scope="col" className="num">Subtotal</th>
                    <th scope="col" className="num">Sales tax</th>
                    <th scope="col" className="num">Sales tax withheld</th>
                    <th scope="col" className="num">Income tax withheld</th>
                    <th scope="col" className="num">Payable</th>
                  </tr>
                </thead>
                <tbody>
                  {doc.lines.map((line) => (
                    <tr key={line.line_no}>
                      <td className="user-text">{line.item}</td>
                      <td>{KIND_TEXT[line.category] ?? line.category}</td>
                      <td className="num">{line.quantity}</td>
                      <td className="num"><Money value={line.rate} /></td>
                      <td className="num"><Money value={line.subtotal} /></td>
                      <td className="num" title={`Charged at ${formatBasisPoints(line.sales_tax_bp)}`}><Money value={line.sales_tax} /></td>
                      <td className="num" title={`Rate ${formatBasisPoints(line.sales_withholding_bp)}`}><Money value={line.sales_tax_withheld} /></td>
                      <td className="num" title={`Rate ${formatBasisPoints(line.income_withholding_bp)}`}><Money value={line.income_tax_withheld} /></td>
                      <td className="num"><Money value={line.payable} /></td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row" colSpan={4}>Totals</th>
                    <td className="num"><Money value={doc.subtotal} /></td>
                    <td className="num"><Money value={doc.sales_tax_total} /></td>
                    <td className="num"><Money value={doc.sales_tax_withheld} /></td>
                    <td className="num"><Money value={doc.income_tax_withheld} /></td>
                    <td className="num"><Money value={doc.payable} strong /></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </Panel>

          <Panel title="Details">
            <dl className={view.details}>
              <div><dt>Dated</dt><dd><DateText value={doc.document_date} /></dd></div>
              <div><dt>Gross value</dt><dd><Money value={doc.gross_total} /></dd></div>
              <div><dt>Payable to the vendor</dt><dd className={view.big}><Money value={doc.payable} strong /></dd></div>
              <div><dt>Vendor at the time</dt><dd>{doc.vendor_registered ? "Registered" : "Not registered"}, {doc.vendor_filer ? "filer" : "non-filer"}</dd></div>
              <div><dt>For</dt><dd className="user-text">{doc.description || null}</dd></div>
            </dl>
          </Panel>

          <Panel title="Receipts">
            <ReceiptPanel kind="purchases" id={id} editable={editable} />
          </Panel>
        </div>

        <aside className={view.rail} aria-label="About this purchase">
          <Panel title="Record">
            <Facts
              items={[
                { label: "Status", value: <Stamp status={doc.status} /> },
                {
                  label: "Voucher",
                  value: doc.voucher ? (
                    <Link href={`/vouchers/${doc.voucher.id}`}>
                      <Identifier value={doc.voucher.number} /> <Stamp status={doc.voucher.status} />
                    </Link>
                  ) : null,
                },
                { label: "Written by", value: doc.created_by_name },
                { label: "Created", value: <Instant value={doc.created_at} /> },
                { label: "Last changed", value: <Instant value={doc.updated_at} /> },
              ]}
            />
          </Panel>
          <Panel title="History">
            <HistoryPanel kind="purchases" id={id} />
          </Panel>
        </aside>
      </div>
      {canGenerate ? <GenerateDialog purchase={doc} open={generating} onClose={() => setGenerating(false)} /> : null}
    </>
  );
}
