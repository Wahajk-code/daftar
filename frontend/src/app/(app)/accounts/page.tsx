import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Accounts } from "./Accounts";

export const metadata: Metadata = { title: "Chart of accounts" };

export default function Page() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <Accounts />
    </Gate>
  );
}
