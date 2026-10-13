"use client";

import type { Vendor } from "@/api/types";
import { BankAccountButton } from "@/components/master/BankAccountButton";
import { ACTIVE_FILTER, MasterCrud, type MasterConfig, type Values } from "@/components/master/MasterCrud";
import { useMe } from "@/components/shell/MeContext";
import { Tag } from "@/components/ui/Stamp";

const registered = (values: Values) => values.is_sales_tax_registered === "true";

export function Vendors() {
  const me = useMe();
  const canWrite = me.role === "admin" || me.role === "accountant";
  const config: MasterConfig<Vendor> = {
    noun: "vendor",
    title: "Vendors",
    description: "The people and companies purchases are bought from. Whether a vendor is registered for sales tax, and whether they are a filer, decide how a purchase is taxed.",
    path: "/vendors",
    columns: [
      { key: "name", header: "Name", cell: (row) => <span className="user-text">{row.name}</span> },
      { key: "reg", header: "Registration", cell: (row) => <Tag tone={row.is_sales_tax_registered ? "positive" : "caution"}>{row.is_sales_tax_registered ? "Registered" : "Not registered"}</Tag>, width: "150px" },
      { key: "filer", header: "Filer", cell: (row) => <Tag tone={row.is_filer ? "positive" : "caution"}>{row.is_filer ? "Filer" : "Non-filer"}</Tag>, width: "110px" },
      { key: "ntn", header: "NTN", cell: (row) => <span className="mono">{row.ntn}</span>, width: "130px" },
      { key: "contact", header: "Contact", cell: (row) => <span className="user-text">{[row.contact_name, row.phone].filter(Boolean).join(", ")}</span> },
      { key: "bank", header: "Bank account", cell: (row) => <span className="mono">{row.bank_account_masked}</span>, width: "190px" },
    ],
    fields: [
      { key: "name", label: "Name", type: "text", required: true },
      { key: "is_sales_tax_registered", label: "Registration", type: "checkbox", checkLabel: "Registered for sales tax", hint: "A registered vendor needs an NTN and an STRN." },
      { key: "is_filer", label: "Filer", type: "checkbox", checkLabel: "On the active taxpayer list (filer)" },
      { key: "ntn", label: "NTN", type: "text", placeholder: "1234567-8", required: false, when: () => true },
      { key: "strn", label: "STRN", type: "text", placeholder: "03-01-8700-123-45", when: registered, hint: "Needed for a registered vendor." },
      { key: "contact_name", label: "Contact person", type: "text" },
      { key: "phone", label: "Phone", type: "text" },
      { key: "email", label: "Email", type: "text" },
      { key: "address", label: "Address", type: "textarea" },
      { key: "bank_name", label: "Bank", type: "text", createOnly: true },
      { key: "bank_account_number", label: "Account number or IBAN", type: "text", createOnly: true, hint: "Stored encrypted. Changing it later needs your password again." },
    ],
    initial: (row) => ({
      name: row?.name ?? "",
      is_sales_tax_registered: row ? String(row.is_sales_tax_registered) : "false",
      is_filer: row ? String(row.is_filer) : "false",
      ntn: row?.ntn ?? "",
      strn: row?.strn ?? "",
      contact_name: row?.contact_name ?? "",
      phone: row?.phone ?? "",
      email: row?.email ?? "",
      address: row?.address ?? "",
      bank_name: "",
      bank_account_number: "",
    }),
    toBody: (values, mode) => {
      const text = (key: string) => values[key]?.trim() || null;
      const body: Record<string, unknown> = {
        name: values.name,
        is_sales_tax_registered: values.is_sales_tax_registered === "true",
        is_filer: values.is_filer === "true",
        ntn: text("ntn"),
        strn: values.is_sales_tax_registered === "true" ? text("strn") : null,
        contact_name: text("contact_name"),
        phone: text("phone"),
        email: text("email"),
        address: text("address"),
      };
      if (mode === "create") {
        body.bank_name = text("bank_name");
        body.bank_account_number = text("bank_account_number");
      }
      return body;
    },
    filters: [
      { key: "q", label: "Search", type: "search", placeholder: "Search names and NTNs" },
      { key: "registered", label: "Registration", type: "select", options: [{ value: "true", label: "Registered" }, { value: "false", label: "Not registered" }] },
      { key: "filer", label: "Filer", type: "select", options: [{ value: "true", label: "Filer" }, { value: "false", label: "Non-filer" }] },
      ACTIVE_FILTER,
    ],
    hasActive: true,
    defaultSort: "name",
    extraActions: canWrite ? (row) => <BankAccountButton vendor={row} /> : undefined,
  };
  return <MasterCrud config={config} />;
}
