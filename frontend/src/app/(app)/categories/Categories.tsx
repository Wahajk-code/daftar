"use client";

import { useAccounts } from "@/api/queries";
import type { Category } from "@/api/types";
import { ACTIVE_FILTER, MasterCrud, SEARCH_FILTER, type MasterConfig } from "@/components/master/MasterCrud";

export function Categories() {
  const accounts = useAccounts();
  const expenseAccounts = (accounts.data ?? []).filter((account) => account.type === "expense" && account.is_postable);
  const names = new Map((accounts.data ?? []).map((account) => [account.id, `${account.code} ${account.name}`]));

  const config: MasterConfig<Category> = {
    noun: "category",
    title: "Expense categories",
    description: "What an expense is for. Each category points at the expense account its voucher is charged to.",
    path: "/categories",
    columns: [
      { key: "name", header: "Name", sortKey: "name", cell: (row) => <span className="user-text">{row.name}</span> },
      { key: "account", header: "Expense account", cell: (row) => names.get(row.account_id) ?? row.account_id },
    ],
    fields: [
      { key: "name", label: "Name", type: "text", required: true },
      {
        key: "account_id",
        label: "Expense account",
        type: "select",
        required: true,
        options: expenseAccounts.map((account) => ({ value: account.id, label: `${account.code} ${account.name}` })),
        hint: "Only expense accounts that can be posted to are offered.",
      },
    ],
    initial: (row) => ({ name: row?.name ?? "", account_id: row ? String(row.account_id) : "" }),
    toBody: (values) => ({ name: values.name, account_id: Number(values.account_id) }),
    filters: [SEARCH_FILTER, ACTIVE_FILTER],
    hasActive: true,
    defaultSort: "name",
  };
  return <MasterCrud config={config} />;
}
