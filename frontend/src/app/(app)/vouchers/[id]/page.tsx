import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { VoucherDetail } from "./VoucherDetail";

export const metadata: Metadata = { title: "Voucher" };

export default async function VoucherPage({ params }: PageProps<"/vouchers/[id]">) {
  const { id } = await params;
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <VoucherDetail id={Number(id)} />
    </Gate>
  );
}
