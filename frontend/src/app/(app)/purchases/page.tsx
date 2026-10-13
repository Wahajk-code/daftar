import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { PurchaseList } from "./PurchaseList";

export const metadata: Metadata = { title: "Purchases" };

export default function PurchasesPage() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <PurchaseList />
    </Gate>
  );
}
