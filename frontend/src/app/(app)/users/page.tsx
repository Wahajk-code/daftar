import type { Metadata } from "next";
import { Gate } from "@/components/shell/Gate";
import { Users } from "./Users";

export const metadata: Metadata = { title: "Users and invites" };

export default function Page() {
  return (
    <Gate roles={["admin"]}>
      <Users />
    </Gate>
  );
}
