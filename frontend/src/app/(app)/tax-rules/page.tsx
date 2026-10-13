import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { TaxRules } from "./TaxRules";

export const metadata: Metadata = { title: "Tax rates" };

export default function Page() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <TaxRules />
    </Gate>
  );
}
