import type { Metadata } from "next";
import { Help } from "./Help";

export const metadata: Metadata = { title: "Help center" };

export default function HelpPage() {
  return <Help />;
}
