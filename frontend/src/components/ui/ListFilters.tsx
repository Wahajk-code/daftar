"use client";

import { IconAdjustmentsHorizontal, IconSearch } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useZone } from "@/components/shell/MeContext";
import { addDays, formatDate, startOfMonth, startOfYear, todayInZone } from "@/lib/dates";
import { formatMoney, isAmount, stripSeparators } from "@/lib/money";
import { useUrlState } from "@/lib/url-state";
import { FilterChips } from "./DataTable";
import { Dropdown } from "./Dropdown";
import { CheckboxField, SelectField, TextField, type Option } from "./Field";
import styles from "./ListFilters.module.css";

export type FilterDef =
  | { key: string; label: string; type: "select"; options: Option[]; placeholder?: string; /** Shown as a row of pills above the list. */ quick?: boolean }
  | { key: string; label: string; type: "date" }
  | { key: string; label: string; type: "amount" }
  | { key: string; label: string; type: "search"; placeholder?: string }
  | { key: string; label: string; type: "checkbox" };

/** The text a filter in use shows in its chip. */
function chipText(def: FilterDef, value: string): string {
  if (def.type === "select") return `${def.label}: ${def.options.find((option) => String(option.value) === value)?.label ?? value}`;
  if (def.type === "date") return `${def.label}: ${formatDate(value)}`;
  if (def.type === "amount") return `${def.label}: ${formatMoney(value)}`;
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
      <IconSearch size={20} stroke={1.5} aria-hidden className={styles.searchIcon} />
      <TextField label={def.label} hideLabel type="search" value={text} placeholder={def.placeholder ?? def.label} onChange={(event) => setText(event.target.value)} />
    </div>
  );
}

/** An amount that is applied when the person leaves the box or presses Enter, so half-typed numbers do not reload the list. */
function AmountBox({ def, value, onCommit }: { def: Extract<FilterDef, { type: "amount" }>; value: string; onCommit: (value: string) => void }) {
  const [text, setText] = useState(value);
  const [seen, setSeen] = useState(value);
  if (seen !== value) {
    setSeen(value);
    setText(value);
  }
  const clean = stripSeparators(text);
  const invalid = clean !== "" && (!isAmount(clean) || clean.startsWith("-"));
  const commit = () => {
    if (clean === value) return;
    if (clean === "" || !invalid) onCommit(clean);
  };
  return (
    <TextField
      label={def.label}
      inputMode="decimal"
      value={text}
      placeholder="0.00"
      error={invalid ? "Enter an amount such as 1500 or 1500.50." : undefined}
      onChange={(event) => setText(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
        }
      }}
    />
  );
}

/**
 * The filters above a list: a search box, the status as a row of pills, and a "Filters" panel for the rest (selects, a date
 * range with quick choices, an amount range). Every value lives in the address bar, the chips show what is on, and one
 * button clears them all. Changing a filter returns to the first page.
 */
export function ListFilters({ defs }: { defs: FilterDef[] }) {
  const url = useUrlState();
  const zone = useZone();
  const search = defs.find((def): def is Extract<FilterDef, { type: "search" }> => def.type === "search");
  const quick = defs.find((def): def is Extract<FilterDef, { type: "select" }> => def.type === "select" && def.quick === true);
  const more = defs.filter((def) => def !== search && def !== quick);
  const active = defs.filter((def) => url.get(def.key) !== "");
  const activeMore = more.filter((def) => url.get(def.key) !== "").length;
  const chips = active.map((def) => ({ key: def.key, label: chipText(def, url.get(def.key)) }));
  const hasDates = defs.some((def) => def.key === "date_from") && defs.some((def) => def.key === "date_to");

  const today = todayInZone(zone);
  const presets = [
    { label: "Today", from: today, to: today },
    { label: "Last 7 days", from: addDays(today, -6), to: today },
    { label: "This month", from: startOfMonth(today), to: today },
    { label: "Last 30 days", from: addDays(today, -29), to: today },
    { label: "This year", from: startOfYear(today), to: today },
  ];

  return (
    <div className={styles.wrap} data-noprint>
      <div className={styles.bar} role="search">
        {search ? <SearchBox def={search} value={url.get(search.key)} onChange={(next) => url.set({ [search.key]: next })} /> : null}

        {quick ? (
          <div className={styles.pills} role="group" aria-label={quick.label}>
            <button type="button" className={styles.pill} aria-pressed={url.get(quick.key) === ""} onClick={() => url.clear([quick.key])}>
              All
            </button>
            {quick.options.map((option) => (
              <button
                key={String(option.value)}
                type="button"
                className={styles.pill}
                aria-pressed={url.get(quick.key) === String(option.value)}
                onClick={() => url.set({ [quick.key]: String(option.value) })}
              >
                {option.label}
              </button>
            ))}
          </div>
        ) : null}

        {more.length > 0 ? (
          <Dropdown
            label="Filters"
            triggerClassName={styles.filterButton}
            width="460px"
            trigger={
              <>
                <IconAdjustmentsHorizontal size={20} stroke={1.5} aria-hidden />
                <span>Filters</span>
                {activeMore > 0 ? <span className={styles.count}>{activeMore}</span> : null}
              </>
            }
          >
            {(close) => (
              <div className={styles.panel}>
                {hasDates ? (
                  <div className={styles.presets} role="group" aria-label="Quick date ranges">
                    {presets.map((preset) => (
                      <button key={preset.label} type="button" className={styles.preset} onClick={() => url.set({ date_from: preset.from, date_to: preset.to })}>
                        {preset.label}
                      </button>
                    ))}
                  </div>
                ) : null}
                <div className={styles.fields}>
                  {more.map((def) => {
                    const value = url.get(def.key);
                    if (def.type === "select") {
                      return (
                        <SelectField key={def.key} label={def.label} options={def.options} placeholder={def.placeholder ?? "All"} value={value} onChange={(event) => url.set({ [def.key]: event.target.value })} />
                      );
                    }
                    if (def.type === "date") {
                      return <TextField key={def.key} label={def.label} type="date" value={value} onChange={(event) => url.set({ [def.key]: event.target.value })} />;
                    }
                    if (def.type === "amount") {
                      return <AmountBox key={def.key} def={def} value={value} onCommit={(next) => url.set({ [def.key]: next })} />;
                    }
                    if (def.type === "checkbox") {
                      return (
                        <CheckboxField key={def.key} label={def.label} checked={value === "true"} onChange={(event) => url.set({ [def.key]: event.target.checked ? "true" : null })} className={styles.check} />
                      );
                    }
                    return null;
                  })}
                </div>
                <div className={styles.panelFoot}>
                  <button type="button" className={styles.reset} onClick={() => url.clear(more.map((def) => def.key))} disabled={activeMore === 0}>
                    Reset these
                  </button>
                  <button type="button" className={styles.done} onClick={close}>
                    Done
                  </button>
                </div>
              </div>
            )}
          </Dropdown>
        ) : null}
      </div>
      <FilterChips chips={chips} onRemove={(key) => url.clear([key])} onClear={() => url.clear(defs.map((def) => def.key))} />
    </div>
  );
}
