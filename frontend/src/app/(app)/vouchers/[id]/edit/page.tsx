import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { EditVoucher } from "./EditVoucher";

export const metadata: Metadata = { title: "Edit voucher" };

export default async function EditVoucherPage({ params }: PageProps<"/vouchers/[id]/edit">) {
  const { id } = await params;
  return (
    <Gate roles={["admin", "accountant"]}>
      <EditVoucher id={Number(id)} />
    </Gate>
  );
}
