import type { Metadata } from "next";
import { PurchaseForm } from "@/components/documents/PurchaseForm";
import { Gate } from "@/components/shell/Gate";
import { PageHeader } from "@/components/ui/Layout";

export const metadata: Metadata = { title: "New purchase" };

export default function NewPurchasePage() {
  return (
    <Gate roles={["admin", "accountant"]}>
      <PageHeader
        title="New purchase"
        back={{ href: "/purchases", label: "Purchases" }}
        description="The tax is worked out by the server as you type; nothing here is trusted from the browser."
      />
      <PurchaseForm />
    </Gate>
  );
}
