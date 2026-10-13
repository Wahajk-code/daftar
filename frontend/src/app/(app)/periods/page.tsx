import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Periods } from "./Periods";

export const metadata: Metadata = { title: "Accounting periods" };

export default function Page() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <Periods />
    </Gate>
  );
}
