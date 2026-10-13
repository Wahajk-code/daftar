import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { EditExpense } from "./EditExpense";

export const metadata: Metadata = { title: "Edit expense" };

export default async function EditExpensePage({ params }: PageProps<"/expenses/[id]/edit">) {
  const { id } = await params;
  return (
    <Gate roles={["admin", "accountant", "staff"]}>
      <EditExpense id={Number(id)} />
    </Gate>
  );
}
