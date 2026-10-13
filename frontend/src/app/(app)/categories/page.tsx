import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Categories } from "./Categories";

export const metadata: Metadata = { title: "Categories" };

export default function Page() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <Categories />
    </Gate>
  );
}
