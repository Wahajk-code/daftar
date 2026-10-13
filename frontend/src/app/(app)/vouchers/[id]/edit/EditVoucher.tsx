"use client";

import { useRecord } from "@/api/queries";
import type { Voucher } from "@/api/types";
import { VoucherForm } from "@/components/documents/VoucherForm";
import { useMe } from "@/components/shell/MeContext";
import { ButtonLink } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/Layout";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/States";

export function EditVoucher({ id }: { id: number }) {
  const me = useMe();
  const voucher = useRecord<Voucher>(["vouchers", id], `/vouchers/${id}`);
  if (voucher.isPending) return <LoadingBlock label="Loading the voucher" />;
  if (voucher.error) return <ErrorState error={voucher.error} onRetry={() => voucher.refetch()} />;
  const editable = voucher.data.status === "draft" && voucher.data.created_by === me.id;
  return (
    <>
      <PageHeader title="Edit voucher" back={{ href: `/vouchers/${id}`, label: "Back to the voucher" }} />
      {editable ? (
        <VoucherForm initial={voucher.data} />
      ) : (
        <EmptyState title="This voucher can no longer be edited" action={<ButtonLink href={`/vouchers/${id}`}>Back to the voucher</ButtonLink>}>
          Only the author can change a voucher, and only while it is a draft. Once it is sent for approval its lines are fixed.
        </EmptyState>
      )}
    </>
  );
}
