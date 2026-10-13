"use client";

import { IconBan, IconCircleCheck, IconPencil } from "@tabler/icons-react";
import Link from "next/link";
import { useState } from "react";
import { api, newIdempotencyKey } from "@/api/client";
import { DOCUMENT_KEYS, codeMap, useAction, useAllCostCenters, useAllProjects, useRecord } from "@/api/queries";
import type { Voucher, VoidResult } from "@/api/types";
import { DocumentActions } from "@/components/documents/DocumentActions";
import { HistoryPanel } from "@/components/documents/Panels";
import { RejectionNotice } from "@/components/documents/RejectionNotice";
import { useMe } from "@/components/shell/MeContext";
import { Button, ButtonLink } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { DateText, Identifier, Instant, Money } from "@/components/ui/Format";
import { Facts, PageHeader, Panel } from "@/components/ui/Layout";
import { Banner, ErrorState, LoadingBlock } from "@/components/ui/States";
import { Stamp } from "@/components/ui/Stamp";
import { voucherTypeLabel } from "@/lib/documents";
import view from "@/components/documents/DocumentView.module.css";
import styles from "./VoucherDetail.module.css";

export function VoucherDetail({ id }: { id: number }) {
  const me = useMe();
  const voucher = useRecord<Voucher>(["vouchers", id], `/vouchers/${id}`);
  const centres = useAllCostCenters();
  const projects = useAllProjects();
  const [dialog, setDialog] = useState<"post" | "void" | null>(null);
  // One key for one attempt: a retry of the same click reuses it, so a double click can never post twice.
  const [attempt, setAttempt] = useState<string>("");

  const post = useAction<void, Voucher>({
    mutationFn: () => api<Voucher>(`/vouchers/${id}/post`, { method: "POST", version: voucher.data?.version, idempotencyKey: attempt }),
    success: (posted) => `Voucher ${posted.number} posted`,
    invalidate: DOCUMENT_KEYS,
  });
  const voidIt = useAction<string, VoidResult>({
    mutationFn: (reason) => api<VoidResult>(`/vouchers/${id}/void`, { method: "POST", version: voucher.data?.version, idempotencyKey: attempt, body: { reason } }),
    success: (result) => `Voucher ${result.voucher.number} voided; reversal ${result.reversal.number} posted`,
    invalidate: DOCUMENT_KEYS,
  });

  if (voucher.isPending) return <LoadingBlock shape="detail" label="Loading the voucher" />;
  if (voucher.error) return <ErrorState error={voucher.error} onRetry={() => voucher.refetch()} />;
  const doc = voucher.data;
  const can = (action: string) => doc.actions.includes(action);
  const editable = doc.created_by === me.id && doc.status === "draft";
  const centreNames = codeMap(centres.data);
  const projectNames = codeMap(projects.data);

  function open(which: "post" | "void") {
    setAttempt(newIdempotencyKey());
    setDialog(which);
  }

  return (
    <>
      <PageHeader
        print
        back={{ href: "/vouchers", label: "Vouchers" }}
        title={<Identifier value={doc.number ?? `${doc.voucher_type} draft ${doc.id}`} voided={doc.status === "void"} />}
        meta={
          <>
            <Stamp status={doc.status} />
            <span>{voucherTypeLabel(doc.voucher_type)}</span>
            <span className="muted">
              Dated <DateText value={doc.document_date} />
            </span>
          </>
        }
        actions={
          editable ? (
            <ButtonLink href={`/vouchers/${id}/edit`} icon={<IconPencil size={18} stroke={1.75} aria-hidden />}>
              Edit
            </ButtonLink>
          ) : undefined
        }
      />

      <div className={view.layout}>
        <div className={view.main}>
          <RejectionNotice kind="vouchers" id={id} status={doc.status} isAuthor={doc.created_by === me.id} />
          {doc.status === "void" ? (
            <Banner tone="negative" title={`Voided: ${doc.void_reason ?? ""}`}>
              {doc.voided_at ? <>Voided <Instant value={doc.voided_at} />. </> : null}
              {doc.reversed_by_id ? <Link href={`/vouchers/${doc.reversed_by_id}`}>See the reversing voucher</Link> : null}
            </Banner>
          ) : null}
          {doc.reversal_of_id ? (
            <Banner tone="info" title={`This reverses ${doc.reversal_of_number}`}>
              It was created when that voucher was voided, with every debit and credit swapped. <Link href={`/vouchers/${doc.reversal_of_id}`}>Open the original</Link>
            </Banner>
          ) : null}

          <div className={styles.noprint}>
            <DocumentActions kind="vouchers" doc={doc}>
              {can("post") ? (
                <Button variant="primary" icon={<IconCircleCheck size={18} stroke={1.75} aria-hidden />} onClick={() => open("post")}>
                  Post voucher
                </Button>
              ) : null}
              {can("void") ? (
                <Button variant="danger" icon={<IconBan size={18} stroke={1.75} aria-hidden />} onClick={() => open("void")}>
                  Void voucher
                </Button>
              ) : null}
            </DocumentActions>
          </div>

          <Panel title="Narration">
            <p className="user-text">{doc.description || <span className="faint">No narration</span>}</p>
          </Panel>

          <Panel title="Lines" flush>
            <div style={{ overflowX: "auto" }}>
              <table className={styles.lines}>
                <caption className="sr-only">Voucher lines</caption>
                <thead>
                  <tr>
                    <th scope="col" className={styles.no}>#</th>
                    <th scope="col">Account</th>
                    <th scope="col">Note</th>
                    <th scope="col">Cost centre</th>
                    <th scope="col">Project</th>
                    <th scope="col" className={`num ${styles.debitHead}`}>Debit</th>
                    <th scope="col" className={`num ${styles.creditHead}`}>Credit</th>
                  </tr>
                </thead>
                <tbody>
                  {doc.lines.map((line) => (
                    <tr key={line.line_no}>
                      <td className={styles.no}>{line.line_no}</td>
                      <td>
                        <span className="ident">{line.account_code}</span> {line.account_name}
                      </td>
                      <td className="user-text">{line.description}</td>
                      <td>{line.cost_center_id ? centreNames.get(line.cost_center_id) : null}</td>
                      <td>{line.project_id ? projectNames.get(line.project_id) : null}</td>
                      <td className={`num ${styles.debitCell}`}>{line.debit !== "0.00" ? <Money value={line.debit} /> : null}</td>
                      <td className={`num ${styles.creditCell}`}>{line.credit !== "0.00" ? <Money value={line.credit} /> : null}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row" colSpan={5}>Totals</th>
                    <td className="num"><Money currency value={doc.total_debit} strong /></td>
                    <td className="num"><Money currency value={doc.total_credit} strong /></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </Panel>

          <div className={styles.signatures} aria-hidden>
            <div><span>Prepared by</span></div>
            <div><span>Approved by</span></div>
            <div><span>Received by</span></div>
          </div>
        </div>

        <aside className={`${view.rail} ${styles.noprint}`} aria-label="About this voucher">
          <Panel title="Record">
            <Facts
              items={[
                { label: "Status", value: <Stamp status={doc.status} /> },
                { label: "Number", value: <Identifier value={doc.number} voided={doc.status === "void"} /> },
                {
                  label: "Made from",
                  value: doc.expense_id ? (
                    <Link href={`/expenses/${doc.expense_id}`}>Expense {doc.expense_id}</Link>
                  ) : doc.purchase_id ? (
                    <Link href={`/purchases/${doc.purchase_id}`}>Purchase {doc.purchase_id}</Link>
                  ) : (
                    "Entered by hand"
                  ),
                },
                { label: "Written by", value: doc.created_by_name },
                { label: "Created", value: <Instant value={doc.created_at} /> },
                { label: "Last changed", value: <Instant value={doc.updated_at} /> },
              ]}
            />
          </Panel>
          <Panel title="History">
            <HistoryPanel kind="vouchers" id={id} />
          </Panel>
        </aside>
      </div>

      <ConfirmDialog
        open={dialog === "post"}
        onClose={() => setDialog(null)}
        title="Post this voucher"
        confirmLabel="Post voucher"
        onConfirm={() => post.mutateAsync()}
        reasonLabel={undefined}
      >
        Posting gives the voucher its permanent number. A posted voucher can never be edited or deleted; if it is wrong it is voided,
        and the books keep both. The expense or purchase it came from is marked posted too.
      </ConfirmDialog>
      <ConfirmDialog
        open={dialog === "void"}
        onClose={() => setDialog(null)}
        title="Void this voucher"
        confirmLabel="Void voucher"
        danger
        reasonLabel="Why is it being voided?"
        reasonHint="Kept with the voucher and shown to everyone who reads it."
        onConfirm={(reason) => voidIt.mutateAsync(reason)}
      >
        A reversing voucher is posted at once with every debit and credit swapped, dated today. This voucher stays on record as void, and
        its source document stays posted. To put it right, enter a new document.
      </ConfirmDialog>
    </>
  );
}
