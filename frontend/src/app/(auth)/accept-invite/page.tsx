import type { Metadata } from "next";
import { AcceptForm } from "./AcceptForm";

export const metadata: Metadata = { title: "Join Daftar" };

export default async function AcceptInvitePage({ searchParams }: PageProps<"/accept-invite">) {
  const { token } = await searchParams;
  return <AcceptForm token={typeof token === "string" ? token : ""} />;
}
