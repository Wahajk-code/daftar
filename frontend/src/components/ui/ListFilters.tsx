"use client";

import { IconSearch } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useUrlState } from "@/lib/url-state";
import { formatDate } from "@/lib/dates";
import { FilterChips } from "./DataTable";
import { CheckboxField, SelectField, TextField, type Option } from "./Field";
import styles from "./ListFilters.module.css";

export type FilterDef =
  | { key: string; label: string; type: "select"; options: Option[]; placeholder?: string }
  | { key: string; label: string; type: "date" }
  | { key: string; label: string; type: "search"; placeholder?: string }
  | { key: string; label: string; type: "checkbox" };

/** The text a filter in use shows in its chip. */
function chipText(def: FilterDef, value: string): string {
  if (def.type === "select") return `${def.label}: ${def.options.find((option) => String(option.value) === value)?.label ?? value}`;
  if (def.type === "date") return `${def.label}: ${formatDate(value)}`;
  if (def.type === "checkbox") return def.label;
  return `${def.label}: ${value}`;
}

/** A search box that waits for a pause in typing before it changes the address. */
function SearchBox({ def, value, onChange }: { def: Extract<FilterDef, { type: "search" }>; value: string; onChange: (value: string) => void }) {
  const [text, setText] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => text !== value && onChange(text), 350);
    return () => window.clearTimeout(timer);
  }, [text, value, onChange]);
  // Clearing the filter elsewhere (a chip, "Clear all") empties the box too.
  const [seen, setSeen] = useState(value);
  if (seen !== value) {
    setSeen(value);
    setText(value);
  }
  return (
    <div className={styles.search}>
      <IconSearch size={16} stroke={1.5} aria-hidden className={styles.searchIcon} />
      <TextField
        label={def.label}
        hideLabel
        type="search"
        value={text}
        placeholder={def.placeholder ?? def.label}
        onChange={(event) => setText(event.target.value)}
      />
    </div>
  );
}

/**
 * The filters above a list. Every value lives in the address bar, the chips show what is on, and one button clears them
 * all. Changing a filter returns to the first page.
 */
export function ListFilters({ defs }: { defs: FilterDef[] }) {
  const url = useUrlState();
  const active = defs.filter((def) => url.get(def.key) !== "");
  const chips = active.map((def) => ({ key: def.key, label: chipText(def, url.get(def.key)) }));

  return (
    <div className={styles.wrap}>
      <div className={styles.bar} role="search">
        {defs.map((def) => {
          const value = url.get(def.key);
          if (def.type === "search") {
            return <SearchBox key={def.key} def={def} value={value} onChange={(next) => url.set({ [def.key]: next })} />;
          }
          if (def.type === "select") {
            return (
              <SelectField
                key={def.key}
                label={def.label}
                options={def.options}
                placeholder={def.placeholder ?? "All"}
                value={value}
                onChange={(event) => url.set({ [def.key]: event.target.value })}
                className={styles.select}
              />
            );
          }
          if (def.type === "date") {
            return (
              <TextField
                key={def.key}
                label={def.label}
                type="date"
                value={value}
                onChange={(event) => url.set({ [def.key]: event.target.value })}
                className={styles.date}
              />
            );
          }
          return (
            <CheckboxField
              key={def.key}
              label={def.label}
              checked={value === "true"}
              onChange={(event) => url.set({ [def.key]: event.target.checked ? "true" : null })}
              className={styles.check}
            />
          );
        })}
      </div>
      <FilterChips chips={chips} onRemove={(key) => url.clear([key])} onClear={() => url.clear(defs.map((def) => def.key))} />
    </div>
  );
}
