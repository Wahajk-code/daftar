import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Vendors } from "./Vendors";

export const metadata: Metadata = { title: "Vendors" };

export default function Page() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <Vendors />
    </Gate>
  );
}
