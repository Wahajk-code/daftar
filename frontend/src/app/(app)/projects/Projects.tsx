"use client";

import type { Project } from "@/api/types";
import { ACTIVE_FILTER, MasterCrud, SEARCH_FILTER, type MasterConfig } from "@/components/master/MasterCrud";

const config: MasterConfig<Project> = {
  noun: "project or product",
  title: "Projects and products",
  description: "Work and goods that expenses can be charged to directly.",
  path: "/projects",
  columns: [
    { key: "code", header: "Code", sortKey: "code", cell: (row) => <span className="mono">{row.code}</span>, width: "140px" },
    { key: "name", header: "Name", sortKey: "name", cell: (row) => <span className="user-text">{row.name}</span> },
    { key: "kind", header: "Kind", sortKey: "kind", cell: (row) => (row.kind === "project" ? "Project" : "Product"), width: "110px" },
  ],
  fields: [
    { key: "code", label: "Code", type: "text", required: true, createOnly: true, hint: "Short and unique, such as PRJ-003. It cannot be changed later." },
    { key: "name", label: "Name", type: "text", required: true },
    {
      key: "kind",
      label: "Kind",
      type: "select",
      required: true,
      createOnly: true,
      options: [
        { value: "project", label: "Project" },
        { value: "product", label: "Product" },
      ],
    },
  ],
  initial: (row) => ({ code: row?.code ?? "", name: row?.name ?? "", kind: row?.kind ?? "project" }),
  toBody: (values, mode) => (mode === "create" ? { code: values.code, name: values.name, kind: values.kind } : { name: values.name }),
  filters: [
    SEARCH_FILTER,
    {
      key: "kind",
      label: "Kind",
      type: "select",
      options: [
        { value: "project", label: "Project" },
        { value: "product", label: "Product" },
      ],
    },
    ACTIVE_FILTER,
  ],
  hasActive: true,
  defaultSort: "code",
};

export function Projects() {
  return <MasterCrud config={config} />;
}
