import type { Metadata } from "next";
import { VoucherForm } from "@/components/documents/VoucherForm";
import { Gate } from "@/components/shell/Gate";
import { PageHeader } from "@/components/ui/Layout";

export const metadata: Metadata = { title: "New voucher" };

export default function NewVoucherPage() {
  return (
    <Gate roles={["admin", "accountant"]}>
      <PageHeader
        title="New voucher"
        back={{ href: "/vouchers", label: "Vouchers" }}
        description="Debits must equal credits before it can be saved."
      />
      <VoucherForm />
    </Gate>
  );
}
