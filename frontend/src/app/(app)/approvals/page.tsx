import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Approvals } from "./Approvals";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return (
    <Gate roles={["admin", "approver"]}>
      <Approvals />
    </Gate>
  );
}
