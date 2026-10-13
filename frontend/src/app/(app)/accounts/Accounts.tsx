"use client";

import { useAllAccounts } from "@/api/queries";
import type { Account } from "@/api/types";
import { ACTIVE_FILTER, MasterCrud, SEARCH_FILTER, type MasterConfig } from "@/components/master/MasterCrud";
import { Tag } from "@/components/ui/Stamp";

const TYPE_TONE = { asset: "info", liability: "caution", equity: "violet", income: "positive", expense: "negative" } as const;

const TYPES = [
  { value: "asset", label: "Asset" },
  { value: "liability", label: "Liability" },
  { value: "equity", label: "Equity" },
  { value: "income", label: "Income" },
  { value: "expense", label: "Expense" },
];

export function Accounts() {
  const all = useAllAccounts();
  const byId = new Map((all.data ?? []).map((account) => [account.id, account]));
  const parents = (all.data ?? []).filter((account) => !account.is_postable);

  const config: MasterConfig<Account> = {
    noun: "account",
    title: "Chart of accounts",
    description: "Where vouchers post to. A parent account only groups its sub-accounts and is never posted to.",
    path: "/accounts",
    columns: [
      {
        key: "code",
        header: "Code",
        sortKey: "code",
        cell: (row) => (
          <span className="ident" style={{ paddingLeft: row.parent_id ? 16 : 0 }}>
            {row.code}
          </span>
        ),
        width: "120px",
      },
      { key: "name", header: "Name", sortKey: "name", primary: true, cell: (row) => <span className="user-text" style={{ fontWeight: row.is_postable ? 500 : 700 }}>{row.name}</span>, title: (row) => row.name, maxWidth: "36ch" },
      { key: "type", header: "Type", sortKey: "type", cell: (row) => <Tag tone={TYPE_TONE[row.type as keyof typeof TYPE_TONE] ?? "neutral"}>{TYPES.find((type) => type.value === row.type)?.label ?? row.type}</Tag>, width: "120px" },
      { key: "parent", header: "Under", cell: (row) => (row.parent_id ? byId.get(row.parent_id)?.code : null), width: "100px" },
      { key: "post", header: "Posting", cell: (row) => <Tag tone={row.is_postable ? "positive" : "neutral"}>{row.is_postable ? "Postable" : "Parent"}</Tag>, width: "110px" },
    ],
    fields: [
      { key: "code", label: "Code", type: "text", required: true, createOnly: true, hint: "Letters, digits, dots and hyphens. It cannot be changed later." },
      { key: "name", label: "Name", type: "text", required: true },
      { key: "type", label: "Type", type: "select", required: true, createOnly: true, options: TYPES },
      {
        key: "parent_id",
        label: "Under",
        type: "select",
        createOnly: true,
        placeholder: "Nothing: a top-level account",
        options: parents.map((account) => ({ value: account.id, label: `${account.code} ${account.name}` })),
        hint: "Only parent accounts can have sub-accounts.",
      },
      { key: "is_postable", label: "Postable", type: "checkbox", checkLabel: "Vouchers can post to this account", hint: "Turn off for a parent that only groups others. An account that already has postings cannot become a parent." },
    ],
    initial: (row) => ({ code: row?.code ?? "", name: row?.name ?? "", type: row?.type ?? "expense", parent_id: row?.parent_id ? String(row.parent_id) : "", is_postable: row ? String(row.is_postable) : "true" }),
    toBody: (values, mode) =>
      mode === "create"
        ? { code: values.code, name: values.name, type: values.type, parent_id: values.parent_id ? Number(values.parent_id) : null, is_postable: values.is_postable === "true" }
        : { name: values.name, is_postable: values.is_postable === "true" },
    filters: [SEARCH_FILTER, { key: "type", label: "Type", type: "select", options: TYPES }, ACTIVE_FILTER],
    hasActive: true,
    defaultSort: "code",
  };
  return <MasterCrud config={config} />;
}
