import type { Metadata } from "next";
import { serverConfig } from "@/lib/server/config";
import { LoginForm, type DemoAccount } from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

/** The four demonstration people, one per role. Shown only when DEMO_MODE is on. */
const DEMO_ACCOUNTS: DemoAccount[] = [
  { email: "admin@daftar.pk", name: "Nadia Qureshi", role: "Admin" },
  { email: "accounts@daftar.pk", name: "Usman Tariq", role: "Accountant" },
  { email: "approver@daftar.pk", name: "Ayesha Siddiqui", role: "Approver" },
  { email: "staff@daftar.pk", name: "Bilal Ahmed", role: "Staff" },
];

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next } = await searchParams;
  return <LoginForm next={typeof next === "string" ? next : undefined} demo={serverConfig.demoMode ? DEMO_ACCOUNTS : []} />;
}
