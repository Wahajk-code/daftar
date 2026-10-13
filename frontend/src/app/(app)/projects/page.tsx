import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Projects } from "./Projects";

export const metadata: Metadata = { title: "Projects and products" };

export default function Page() {
  return (
    <Gate roles={["admin", "accountant", "approver"]}>
      <Projects />
    </Gate>
  );
}
