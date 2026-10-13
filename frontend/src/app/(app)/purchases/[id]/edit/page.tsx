import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { EditPurchase } from "./EditPurchase";

export const metadata: Metadata = { title: "Edit purchase" };

export default async function EditPurchasePage({ params }: PageProps<"/purchases/[id]/edit">) {
  const { id } = await params;
  return (
    <Gate roles={["admin", "accountant"]}>
      <EditPurchase id={Number(id)} />
    </Gate>
  );
}
