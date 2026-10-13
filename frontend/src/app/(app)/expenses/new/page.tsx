import type { Metadata } from "next";
import { ExpenseForm } from "@/components/documents/ExpenseForm";
import { Gate } from "@/components/shell/Gate";
import { PageHeader } from "@/components/ui/Layout";

export const metadata: Metadata = { title: "New expense" };

export default function NewExpensePage() {
  return (
    <Gate roles={["admin", "accountant", "staff"]}>
      <PageHeader
        title="New expense"
        back={{ href: "/expenses", label: "Expenses" }}
        description="Save it as a draft, then send it for approval when it is ready."
      />
      <ExpenseForm />
    </Gate>
  );
}
