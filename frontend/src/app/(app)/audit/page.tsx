import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { AuditLog } from "./AuditLog";

export const metadata: Metadata = { title: "Audit log" };

export default function Page() {
  return (
    <Gate roles={["admin"]}>
      <AuditLog />
    </Gate>
  );
}
