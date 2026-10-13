"use client";

import { useRecord } from "@/api/queries";
import type { Purchase } from "@/api/types";
import { PurchaseForm } from "@/components/documents/PurchaseForm";
import { useMe } from "@/components/shell/MeContext";
import { ButtonLink } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/Layout";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/States";

export function EditPurchase({ id }: { id: number }) {
  const me = useMe();
  const purchase = useRecord<Purchase>(["purchases", id], `/purchases/${id}`);
  if (purchase.isPending) return <LoadingBlock shape="form" label="Loading the purchase" />;
  if (purchase.error) return <ErrorState error={purchase.error} onRetry={() => purchase.refetch()} />;
  const editable = purchase.data.status === "draft" && purchase.data.created_by === me.id;
  return (
    <>
      <PageHeader title="Edit purchase" back={{ href: `/purchases/${id}`, label: "Back to the purchase" }} />
      {editable ? (
        <PurchaseForm initial={purchase.data} />
      ) : (
        <EmptyState title="This purchase can no longer be edited" action={<ButtonLink href={`/purchases/${id}`}>Back to the purchase</ButtonLink>}>
          Only the author can change a purchase, and only while it is a draft.
        </EmptyState>
      )}
    </>
  );
}
