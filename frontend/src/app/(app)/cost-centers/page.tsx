import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { CostCenters } from "./CostCenters";

export const metadata: Metadata = { title: "Cost centres" };

export default function Page() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <CostCenters />
    </Gate>
  );
}
