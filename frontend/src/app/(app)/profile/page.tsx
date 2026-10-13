import type { Metadata } from "next";
import { Profile } from "./Profile";

export const metadata: Metadata = { title: "Your account" };

export default function Page() {
  return <Profile />;
}
