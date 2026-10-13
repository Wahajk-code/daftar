"use client";

import { IconPencil, IconPlus } from "@tabler/icons-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { REFERENCE_ROOT, useAction, usePage } from "@/api/queries";
import { useMe } from "@/components/shell/MeContext";
import { Button } from "@/components/ui/Button";
import { DataTable, Pagination, type Column } from "@/components/ui/DataTable";
import { Dialog } from "@/components/ui/Dialog";
import { CheckboxField, SelectField, TextAreaField, TextField, type Option } from "@/components/ui/Field";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { ListFilters, type FilterDef } from "@/components/ui/ListFilters";
import { Requirements } from "@/components/ui/Requirements";
import { Banner } from "@/components/ui/States";
import { Tag } from "@/components/ui/Stamp";
import { PAGE_SIZE, useUrlState } from "@/lib/url-state";
import styles from "./MasterCrud.module.css";

export type Values = Record<string, string>;

export interface FieldSpec {
  key: string;
  label: string;
  type: "text" | "textarea" | "select" | "checkbox" | "date" | "percent";
  options?: Option[];
  placeholder?: string;
  hint?: string;
  required?: boolean;
  /** Only asked for when creating: the value is fixed afterwards (a code, a type). */
  createOnly?: boolean;
  /** Shown only while this is true of the other values, such as a field that applies to one kind of rule. */
  when?: (values: Values) => boolean;
  /** For a checkbox: its text. */
  checkLabel?: string;
}

export interface Row {
  id: number;
  version: number;
  is_active?: boolean;
}

export interface MasterConfig<T extends Row> {
  /** Singular and plural nouns, sentence case: "cost centre", "Cost centres". */
  noun: string;
  title: string;
  description: string;
  path: string;
  columns: Column<T>[];
  fields: FieldSpec[];
  initial: (row?: T) => Values;
  toBody: (values: Values, mode: "create" | "edit") => Record<string, unknown>;
  filters: FilterDef[];
  /** Does the record have an active flag (and so Deactivate and Activate)? */
  hasActive: boolean;
  /** Called with the saved row's cache keys to drop besides the lists. */
  defaultSort: string;
  /** Extra content under the header, such as a note about a risk. */
  notice?: ReactNode;
  extraActions?: (row: T) => ReactNode;
}

function FormFields({ fields, values, set, error, mode }: { fields: FieldSpec[]; values: Values; set: (key: string, value: string) => void; error: ApiError | null; mode: "create" | "edit" }) {
  return (
    <>
      {fields
        .filter((field) => (mode === "create" || !field.createOnly) && (!field.when || field.when(values)))
        .map((field) => {
          const problem = error?.fieldMessage(field.key);
          if (field.type === "select") {
            return (
              <SelectField key={field.key} label={field.label} options={field.options ?? []} placeholder={field.placeholder ?? "Choose"} value={values[field.key] ?? ""} onChange={(event) => set(field.key, event.target.value)} error={problem} hint={field.hint} required={field.required} />
            );
          }
          if (field.type === "checkbox") {
            return <CheckboxField key={field.key} label={field.checkLabel ?? field.label} hint={field.hint} checked={values[field.key] === "true"} onChange={(event) => set(field.key, event.target.checked ? "true" : "false")} />;
          }
          if (field.type === "textarea") {
            return <TextAreaField key={field.key} label={field.label} value={values[field.key] ?? ""} onChange={(event) => set(field.key, event.target.value)} error={problem} hint={field.hint} required={field.required} />;
          }
          return (
            <TextField
              key={field.key}
              label={field.label}
              type={field.type === "date" ? "date" : "text"}
              inputMode={field.type === "percent" ? "decimal" : undefined}
              placeholder={field.placeholder}
              value={values[field.key] ?? ""}
              onChange={(event) => set(field.key, event.target.value)}
              error={problem}
              hint={field.hint}
              required={field.required}
            />
          );
        })}
    </>
  );
}

/**
 * One screen for the simple master-data lists: find a row, add one, change one, switch it off and on again. Nothing is
 * ever deleted. Only Accountants and Admins can change anything; the others read.
 */
export function MasterCrud<T extends Row>({ config }: { config: MasterConfig<T> }) {
  const me = useMe();
  const url = useUrlState();
  const canWrite = me.role === "admin" || me.role === "accountant";
  const [editing, setEditing] = useState<{ mode: "create" } | { mode: "edit"; row: T } | null>(null);
  const [values, setValues] = useState<Values>({});

  const query: Record<string, string | number | null> = { sort: url.get("sort"), limit: PAGE_SIZE, offset: Number(url.get("offset") || 0) };
  for (const filter of config.filters) query[filter.key] = url.get(filter.key);
  const list = usePage<T>(config.path, query);

  const save = useAction<void, T>({
    mutationFn: () => {
      if (!editing) throw new Error("nothing is being edited");
      if (editing.mode === "create") return api<T>(config.path, { method: "POST", body: config.toBody(values, "create") });
      return api<T>(`${config.path}/${editing.row.id}`, { method: "PATCH", body: config.toBody(values, "edit"), version: editing.row.version });
    },
    success: () => (editing?.mode === "create" ? `${capital(config.noun)} added` : `${capital(config.noun)} saved`),
    invalidate: [["list"], [REFERENCE_ROOT]],
    onSuccess: () => setEditing(null),
  });

  const toggle = useAction<T, T>({
    mutationFn: (row) => api<T>(`${config.path}/${row.id}/${row.is_active ? "deactivate" : "activate"}`, { method: "POST" }),
    success: (row) => `${capital(config.noun)} ${row.is_active ? "activated" : "deactivated"}`,
    invalidate: [["list"], [REFERENCE_ROOT]],
  });

  function open(next: { mode: "create" } | { mode: "edit"; row: T }) {
    save.reset();
    setValues(config.initial(next.mode === "edit" ? next.row : undefined));
    setEditing(next);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  const columns: Column<T>[] = [
    ...config.columns,
    ...(config.hasActive ? [{ key: "active", header: "Status", cell: (row: T) => <Tag tone={row.is_active ? "positive" : "neutral"}>{row.is_active ? "Active" : "Inactive"}</Tag>, width: "110px" } as Column<T>] : []),
    ...(canWrite
      ? [
          {
            key: "actions",
            header: "Actions",
            width: config.hasActive ? "200px" : "110px",
            cell: (row: T) => (
              <span className={styles.rowActions}>
                {config.extraActions?.(row)}
                <Button small variant="secondary" icon={<IconPencil size={16} stroke={1.75} aria-hidden />} onClick={() => open({ mode: "edit", row })}>
                  Edit
                </Button>
                {config.hasActive ? (
                  <Button small variant="secondary" pending={toggle.isPending && toggle.variables?.id === row.id} onClick={() => toggle.mutate(row)}>
                    {row.is_active ? "Deactivate" : "Activate"}
                  </Button>
                ) : null}
              </span>
            ),
          } as Column<T>,
        ]
      : []),
  ];

  const error = save.error instanceof ApiError ? save.error : null;
  // The required fields that are showing and still empty, live: the button waits for them and the form names them.
  const missing = editing
    ? config.fields
        .filter((field) => field.required && (editing.mode === "create" || !field.createOnly) && (!field.when || field.when(values)))
        .filter((field) => (values[field.key] ?? "").trim() === "")
        .map((field) => field.label)
    : [];

  return (
    <>
      <PageHeader
        title={config.title}
        description={config.description}
        actions={
          canWrite ? (
            <Button variant="primary" icon={<IconPlus size={18} stroke={1.75} aria-hidden />} onClick={() => open({ mode: "create" })}>
              New {config.noun}
            </Button>
          ) : undefined
        }
      />
      {config.notice}
      <Panel flush>
        <ListFilters defs={config.filters} />
        <DataTable
          caption={config.title}
          columns={columns}
          rows={list.data?.items}
          getKey={(row) => row.id}
          onRowClick={canWrite ? (row) => open({ mode: "edit", row }) : undefined}
          loading={list.isPending}
          error={list.error}
          onRetry={() => list.refetch()}
          sort={url.get("sort") || config.defaultSort}
          onSort={(sort) => url.set({ sort })}
          empty={{ title: `No ${config.noun}s match`, hint: canWrite ? "Change the filters, or add one." : "Change the filters.", action: canWrite ? <Button onClick={() => open({ mode: "create" })}>New {config.noun}</Button> : undefined }}
        />
        {list.data ? <Pagination total={list.data.total} limit={PAGE_SIZE} offset={Number(url.get("offset") || 0)} onOffset={(offset) => url.set({ offset })} noun={`${config.noun}s`} /> : null}
      </Panel>

      <Dialog open={editing !== null} onClose={() => !save.isPending && setEditing(null)} title={editing?.mode === "create" ? `New ${config.noun}` : `Edit ${config.noun}`}>
        <form className={styles.form} onSubmit={submit} noValidate>
          {error && error.fields.length === 0 ? (
            <Banner tone="negative" title="Could not save">
              {messageFor(error)}
            </Banner>
          ) : null}
          {editing ? <FormFields fields={config.fields} values={values} set={(key, value) => setValues((current) => ({ ...current, [key]: value }))} error={error} mode={editing.mode} /> : null}
          <div className={styles.actions}>
            <Requirements items={missing} />
            <Button onClick={() => setEditing(null)} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" pending={save.isPending} disabled={missing.length > 0}>
              Save {config.noun}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}

function capital(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const ACTIVE_FILTER: FilterDef = {
  key: "is_active",
  label: "Status",
  type: "select",
  options: [
    { value: "true", label: "Active" },
    { value: "false", label: "Inactive" },
  ],
};

export const SEARCH_FILTER: FilterDef = { key: "q", label: "Search", type: "search" };
