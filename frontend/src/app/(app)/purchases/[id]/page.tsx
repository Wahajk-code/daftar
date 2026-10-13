import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { PurchaseDetail } from "./PurchaseDetail";

export const metadata: Metadata = { title: "Purchase" };

export default async function PurchasePage({ params }: PageProps<"/purchases/[id]">) {
  const { id } = await params;
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <PurchaseDetail id={Number(id)} />
    </Gate>
  );
}
