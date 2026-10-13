"use client";

import { IconArrowBackUp, IconCheck, IconSend, IconX } from "@tabler/icons-react";
import { useState } from "react";
import { api } from "@/api/client";
import { ApiError } from "@/api/errors";
import { DOCUMENT_KEYS, useAction } from "@/api/queries";
import type { DocumentStatus } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { Banner } from "@/components/ui/States";
import { KIND_LABEL, type Kind } from "@/lib/documents";

export interface ActionableDocument {
  id: number;
  version: number;
  status: DocumentStatus;
  actions: string[];
}

/**
 * The moves a person can make on a document right now, as the API lists them in `actions`: send for approval, approve,
 * reject (a comment is required), reopen. Nothing here decides what is allowed; the API does, and says why when it refuses.
 * A refusal that lists missing pieces (an incomplete document) is shown under the buttons so the person can fix them.
 */
export function DocumentActions({ kind, doc, children }: { kind: Kind; doc: ActionableDocument; children?: React.ReactNode }) {
  const noun = KIND_LABEL[kind].singular.toLowerCase();
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [problem, setProblem] = useState<ApiError | null>(null);

  const move = useAction<{ action: string; comment?: string }, unknown>({
    mutationFn: ({ action, comment }) =>
      api(`/${kind}/${doc.id}/${action}`, {
        method: "POST",
        version: doc.version,
        body: comment !== undefined ? { comment } : undefined,
      }),
    success: (_, { action }) =>
      ({ submit: `${KIND_LABEL[kind].singular} sent for approval`, approve: `${KIND_LABEL[kind].singular} approved`, reject: `${KIND_LABEL[kind].singular} rejected`, reopen: `${KIND_LABEL[kind].singular} reopened` })[action] ?? "Done",
    invalidate: DOCUMENT_KEYS,
  });

  async function run(action: string, comment?: string) {
    setProblem(null);
    try {
      await move.mutateAsync({ action, comment });
    } catch (error) {
      if (error instanceof ApiError && error.fields.length > 0) setProblem(error);
      throw error;
    }
  }

  const can = (action: string) => doc.actions.includes(action);
  const pendingAction = move.isPending ? move.variables?.action : undefined;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
        {can("submit") ? (
          <Button variant="primary" icon={<IconSend size={16} stroke={1.75} aria-hidden />} pending={pendingAction === "submit"} onClick={() => run("submit").catch(() => undefined)}>
            Send for approval
          </Button>
        ) : null}
        {can("approve") ? (
          <Button variant="primary" icon={<IconCheck size={16} stroke={1.75} aria-hidden />} onClick={() => setDialog("approve")}>
            Approve
          </Button>
        ) : null}
        {can("reject") ? (
          <Button variant="danger" icon={<IconX size={16} stroke={1.75} aria-hidden />} onClick={() => setDialog("reject")}>
            Reject
          </Button>
        ) : null}
        {can("reopen") ? (
          <Button icon={<IconArrowBackUp size={16} stroke={1.75} aria-hidden />} pending={pendingAction === "reopen"} onClick={() => run("reopen").catch(() => undefined)}>
            Reopen for editing
          </Button>
        ) : null}
        {children}
      </div>

      {problem ? (
        <Banner tone="negative" title={problem.detail || "This is not complete yet"}>
          <ul style={{ margin: 0, paddingLeft: "1.2em" }}>
            {problem.fields.map((field) => (
              <li key={`${field.field}-${field.message}`}>{field.message}</li>
            ))}
          </ul>
        </Banner>
      ) : null}

      <ConfirmDialog
        open={dialog === "approve"}
        onClose={() => setDialog(null)}
        title={`Approve this ${noun}`}
        confirmLabel="Approve"
        reasonLabel="Comment (optional)"
        reasonRequired={false}
        onConfirm={(comment) => run("approve", comment || undefined)}
      >
        Once approved, an accountant can turn it into a voucher. You can add a note that stays in the history.
      </ConfirmDialog>
      <ConfirmDialog
        open={dialog === "reject"}
        onClose={() => setDialog(null)}
        title={`Reject this ${noun}`}
        confirmLabel="Reject"
        danger
        reasonLabel="Why is it being rejected?"
        reasonHint="The author reads this in the history, so say what to change."
        onConfirm={(comment) => run("reject", comment)}
      >
        The author can reopen it, change it and send it again.
      </ConfirmDialog>
    </div>
  );
}
