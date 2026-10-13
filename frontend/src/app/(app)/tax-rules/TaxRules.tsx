"use client";

import type { TaxRule } from "@/api/types";
import { MasterCrud, type MasterConfig, type Values } from "@/components/master/MasterCrud";
import { DateText } from "@/components/ui/Format";
import { Banner } from "@/components/ui/States";
import { bpToPercent, formatBasisPoints, percentToBp } from "@/lib/money";

const CATEGORIES = [
  { value: "goods", label: "Goods" },
  { value: "services", label: "Services" },
  { value: "contracts", label: "Contracts" },
  { value: "any", label: "Any kind of payment" },
];

const isSales = (values: Values) => values.tax_type === "sales_tax_withholding";

const config: MasterConfig<TaxRule> = {
  noun: "tax rate",
  title: "Tax rates",
  description: "The withholding rates used to price purchases. A purchase keeps the rate in force on its date, so changing a rate here never changes an old purchase.",
  path: "/tax-rules",
  columns: [
    { key: "type", header: "Tax", sortKey: "tax_type", cell: (row) => (row.tax_type === "sales_tax_withholding" ? "Sales tax withheld" : "Income tax withheld"), width: "170px" },
    {
      key: "who",
      header: "Applies to",
      cell: (row) => (row.tax_type === "sales_tax_withholding" ? (row.supplier_registered ? "Registered suppliers" : "Unregistered suppliers") : row.supplier_filer ? "Filers" : "Non-filers"),
      width: "170px",
    },
    { key: "category", header: "Payment", cell: (row) => CATEGORIES.find((category) => category.value === row.category)?.label ?? row.category, width: "150px" },
    { key: "rate", header: "Rate", numeric: true, sortKey: "rate_bp", cell: (row) => formatBasisPoints(row.rate_bp), width: "90px" },
    { key: "from", header: "From", sortKey: "effective_from", cell: (row) => <DateText value={row.effective_from} />, width: "120px" },
    { key: "to", header: "Until", cell: (row) => (row.effective_to ? <DateText value={row.effective_to} /> : <span className="faint">Open</span>), width: "120px" },
    { key: "source", header: "Source", cell: (row) => <span className="user-text">{row.source}</span>, title: (row) => row.source, maxWidth: "44ch" },
  ],
  fields: [
    {
      key: "tax_type",
      label: "Tax",
      type: "select",
      required: true,
      createOnly: true,
      options: [
        { value: "sales_tax_withholding", label: "Sales tax withheld" },
        { value: "income_tax_withholding", label: "Income tax withheld" },
      ],
    },
    {
      key: "supplier_registered",
      label: "Supplier is registered for sales tax",
      type: "select",
      required: true,
      createOnly: true,
      when: isSales,
      options: [
        { value: "true", label: "Registered" },
        { value: "false", label: "Not registered" },
      ],
    },
    {
      key: "supplier_filer",
      label: "Supplier is on the active taxpayer list",
      type: "select",
      required: true,
      createOnly: true,
      when: (values) => values.tax_type === "income_tax_withholding",
      options: [
        { value: "true", label: "Filer" },
        { value: "false", label: "Non-filer" },
      ],
    },
    { key: "category", label: "Kind of payment", type: "select", required: true, createOnly: true, options: CATEGORIES },
    { key: "rate", label: "Rate (percent)", type: "percent", required: true, hint: "For example 4.5 for 4.5 per cent." },
    { key: "effective_from", label: "In force from", type: "date", required: true, createOnly: true },
    { key: "effective_to", label: "In force until", type: "date", hint: "Leave empty while the rate is still current." },
    { key: "source", label: "Where the rate comes from", type: "textarea", required: true, hint: "The provision or notice, and how it was checked. Kept with the rate." },
  ],
  initial: (row) => ({
    tax_type: row?.tax_type ?? "sales_tax_withholding",
    supplier_registered: row ? String(row.supplier_registered) : "true",
    supplier_filer: row ? String(row.supplier_filer) : "true",
    category: row?.category ?? "any",
    rate: row ? bpToPercent(row.rate_bp) : "",
    effective_from: row?.effective_from ?? "",
    effective_to: row?.effective_to ?? "",
    source: row?.source ?? "",
  }),
  toBody: (values, mode) => {
    const rate_bp = percentToBp(values.rate);
    if (mode === "edit") return { rate_bp, effective_to: values.effective_to || null, source: values.source };
    return {
      tax_type: values.tax_type,
      ...(isSales(values) ? { supplier_registered: values.supplier_registered === "true" } : { supplier_filer: values.supplier_filer === "true" }),
      category: values.category,
      rate_bp,
      effective_from: values.effective_from,
      effective_to: values.effective_to || null,
      source: values.source,
    };
  },
  filters: [
    {
      key: "tax_type",
      label: "Tax",
      type: "select",
      options: [
        { value: "sales_tax_withholding", label: "Sales tax withheld" },
        { value: "income_tax_withholding", label: "Income tax withheld" },
      ],
    },
    { key: "category", label: "Payment", type: "select", options: CATEGORIES },
    { key: "active_on", label: "In force on", type: "date" },
  ],
  hasActive: false,
  defaultSort: "-effective_from",
  notice: (
    <div style={{ marginBottom: "var(--space-4)" }}>
      <Banner tone="caution" title="Check these against the current Finance Act">
        The starting rates were entered as a guide and are marked as unverified in their source. Whoever keeps the books should confirm each one
        before relying on it.
      </Banner>
    </div>
  ),
};

export function TaxRules() {
  return <MasterCrud config={config} />;
}
