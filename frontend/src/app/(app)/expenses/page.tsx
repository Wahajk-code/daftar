import type { Metadata } from "next";
import { ExpenseList } from "./ExpenseList";

export const metadata: Metadata = { title: "Expenses" };

export default function ExpensesPage() {
  return <ExpenseList />;
}
