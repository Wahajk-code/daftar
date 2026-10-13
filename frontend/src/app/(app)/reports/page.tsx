import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Reports } from "./Reports";

export const metadata: Metadata = { title: "Reports" };

export default function ReportsPage() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <Reports />
    </Gate>
  );
}
