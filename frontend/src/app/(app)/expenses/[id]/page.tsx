import type { Metadata } from "next";
import { ExpenseDetail } from "./ExpenseDetail";

export const metadata: Metadata = { title: "Expense" };

export default async function ExpensePage({ params }: PageProps<"/expenses/[id]">) {
  const { id } = await params;
  return <ExpenseDetail id={Number(id)} />;
}
