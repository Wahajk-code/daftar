import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { VoucherList } from "./VoucherList";

export const metadata: Metadata = { title: "Vouchers" };

export default function VouchersPage() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <VoucherList />
    </Gate>
  );
}
