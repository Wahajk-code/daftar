"use client";

import { IconFilePlus, IconPencil } from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/api/client";
import { DOCUMENT_KEYS, codeMap, useAction, useAllCostCenters, useAllProjects, useRecord } from "@/api/queries";
import type { Expense, Voucher } from "@/api/types";
import { DocumentActions } from "@/components/documents/DocumentActions";
import { DuplicatePanel, HistoryPanel, ReceiptPanel } from "@/components/documents/Panels";
import { RejectionNotice } from "@/components/documents/RejectionNotice";
import { useMe } from "@/components/shell/MeContext";
import { Button, ButtonLink } from "@/components/ui/Button";
import { DateText, Identifier, Instant, Money } from "@/components/ui/Format";
import { Facts, PageHeader, Panel } from "@/components/ui/Layout";
import { ErrorState, LoadingBlock } from "@/components/ui/States";
import { Stamp } from "@/components/ui/Stamp";
import { paymentLabel } from "@/lib/documents";
import { formatBasisPoints } from "@/lib/money";
import styles from "@/components/documents/DocumentView.module.css";

export function ExpenseDetail({ id }: { id: number }) {
  const me = useMe();
  const router = useRouter();
  const expense = useRecord<Expense>(["expenses", id], `/expenses/${id}`);
  const centres = useAllCostCenters();
  const projects = useAllProjects();

  const generate = useAction<void, Voucher>({
    mutationFn: () => api<Voucher>(`/expenses/${id}/generate-voucher`, { method: "POST" }),
    success: "Voucher created",
    invalidate: DOCUMENT_KEYS,
    onSuccess: (voucher) => router.push(`/vouchers/${voucher.id}`),
  });

  if (expense.isPending) return <LoadingBlock shape="detail" label="Loading the expense" />;
  if (expense.error) return <ErrorState error={expense.error} onRetry={() => expense.refetch()} />;
  const doc = expense.data;
  const isAuthor = doc.created_by === me.id;
  const editable = isAuthor && doc.status === "draft";
  const canGenerate = (me.role === "admin" || me.role === "accountant") && doc.status === "approved" && !doc.voucher;
  const centreNames = codeMap(centres.data);
  const projectNames = codeMap(projects.data);

  return (
    <>
      <PageHeader
        print
        back={{ href: "/expenses", label: "Expenses" }}
        title={<span className="user-text">{doc.description || doc.category_name}</span>}
        meta={
          <>
            <Stamp status={doc.status} />
            <span>{doc.expense_type === "direct" ? "Direct expense" : "Indirect expense"}</span>
            <span className="muted">Expense {doc.id}</span>
          </>
        }
        actions={
          editable ? (
            <ButtonLink href={`/expenses/${id}/edit`} icon={<IconPencil size={18} stroke={1.75} aria-hidden />}>
              Edit
            </ButtonLink>
          ) : undefined
        }
      />

      <div className={styles.layout}>
        <div className={styles.main}>
          <RejectionNotice kind="expenses" id={id} status={doc.status} isAuthor={isAuthor} />
          <DuplicatePanel kind="expenses" id={id} />
          <DocumentActions kind="expenses" doc={doc}>
            {canGenerate ? (
              <Button variant="primary" icon={<IconFilePlus size={18} stroke={1.75} aria-hidden />} pending={generate.isPending} onClick={() => generate.mutate()}>
                Generate payment voucher
              </Button>
            ) : null}
          </DocumentActions>

          <Panel title="Details">
            <dl className={styles.details}>
              <div>
                <dt>Amount</dt>
                <dd className={styles.big}>
                  <Money value={doc.amount} strong currency={doc.currency} />
                </dd>
              </div>
              <div>
                <dt>Tax included</dt>
                <dd>
                  <Money value={doc.tax_amount} />
                </dd>
              </div>
              <div>
                <dt>Dated</dt>
                <dd>
                  <DateText value={doc.document_date} />
                </dd>
              </div>
              <div>
                <dt>Category</dt>
                <dd>{doc.category_name}</dd>
              </div>
              <div>
                <dt>Paid by</dt>
                <dd>{paymentLabel(doc.payment_method)}</dd>
              </div>
              {doc.expense_type === "direct" ? (
                <div>
                  <dt>Charged to</dt>
                  <dd>
                    {doc.cost_center_id ? centreNames.get(doc.cost_center_id) : doc.project_id ? projectNames.get(doc.project_id) : null}
                  </dd>
                </div>
              ) : null}
            </dl>
          </Panel>

          {doc.expense_type === "indirect" ? (
            <Panel title="How it is shared" flush>
              <table className={styles.split}>
                <caption className="sr-only">The cost centres this expense is charged to</caption>
                <thead>
                  <tr>
                    <th scope="col">Cost centre</th>
                    <th scope="col" className="num">{doc.allocation_method === "percentage" ? "Share" : "Method"}</th>
                    <th scope="col" className="num">Charged</th>
                  </tr>
                </thead>
                <tbody>
                  {doc.allocations.map((row) => (
                    <tr key={row.cost_center_id}>
                      <td>{centreNames.get(row.cost_center_id) ?? row.cost_center_code}</td>
                      <td className="num">{row.basis_points !== null ? formatBasisPoints(row.basis_points) : "Fixed"}</td>
                      <td className="num"><Money value={row.amount} /></td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row" colSpan={2}>Total</th>
                    <td className="num"><Money currency value={doc.amount} strong /></td>
                  </tr>
                </tfoot>
              </table>
            </Panel>
          ) : null}

          <Panel title="Receipts" noPrint>
            <ReceiptPanel kind="expenses" id={id} editable={editable} />
          </Panel>
        </div>

        <aside className={styles.rail} aria-label="About this expense">
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
          <Panel title="History" noPrint>
            <HistoryPanel kind="expenses" id={id} />
          </Panel>
        </aside>
      </div>
    </>
  );
}
