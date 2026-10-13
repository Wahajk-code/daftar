"use client";

import { useRecord } from "@/api/queries";
import type { Expense } from "@/api/types";
import { ExpenseForm } from "@/components/documents/ExpenseForm";
import { useMe } from "@/components/shell/MeContext";
import { ButtonLink } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/Layout";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/States";

export function EditExpense({ id }: { id: number }) {
  const me = useMe();
  const expense = useRecord<Expense>(["expenses", id], `/expenses/${id}`);
  if (expense.isPending) return <LoadingBlock shape="form" label="Loading the expense" />;
  if (expense.error) return <ErrorState error={expense.error} onRetry={() => expense.refetch()} />;
  const editable = expense.data.status === "draft" && expense.data.created_by === me.id;
  return (
    <>
      <PageHeader title="Edit expense" back={{ href: `/expenses/${id}`, label: "Back to the expense" }} />
      {editable ? (
        <ExpenseForm initial={expense.data} />
      ) : (
        <EmptyState title="This expense can no longer be edited" action={<ButtonLink href={`/expenses/${id}`}>Back to the expense</ButtonLink>}>
          Only the author can change an expense, and only while it is a draft.
        </EmptyState>
      )}
    </>
  );
}
