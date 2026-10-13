"use client";

import type { CostCenter } from "@/api/types";
import { ACTIVE_FILTER, MasterCrud, SEARCH_FILTER, type MasterConfig } from "@/components/master/MasterCrud";

const config: MasterConfig<CostCenter> = {
  noun: "cost centre",
  title: "Cost centres",
  description: "The parts of the business that costs are charged to. Nothing is deleted: a cost centre that is no longer used is deactivated.",
  path: "/cost-centers",
  columns: [
    { key: "code", header: "Code", sortKey: "code", cell: (row) => <span className="mono">{row.code}</span>, width: "140px" },
    { key: "name", header: "Name", sortKey: "name", cell: (row) => <span className="user-text">{row.name}</span> },
  ],
  fields: [
    { key: "code", label: "Code", type: "text", required: true, createOnly: true, hint: "Short and unique, such as HO. It cannot be changed later." },
    { key: "name", label: "Name", type: "text", required: true },
  ],
  initial: (row) => ({ code: row?.code ?? "", name: row?.name ?? "" }),
  toBody: (values, mode) => (mode === "create" ? { code: values.code, name: values.name } : { name: values.name }),
  filters: [SEARCH_FILTER, ACTIVE_FILTER],
  hasActive: true,
  defaultSort: "code",
};

export function CostCenters() {
  return <MasterCrud config={config} />;
}
