import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Settings } from "./Settings";

export const metadata: Metadata = { title: "Accounting settings" };

export default function Page() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <Settings />
    </Gate>
  );
}
