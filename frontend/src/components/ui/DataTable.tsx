"use client";

import { IconArrowDown, IconArrowUp, IconArrowsSort, IconChevronLeft, IconChevronRight, IconX } from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import type { MouseEvent, ReactNode } from "react";
import { Button } from "./Button";
import { EmptyState, ErrorState, SkeletonRows } from "./States";
import styles from "./DataTable.module.css";

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Figures line up on the right. */
  numeric?: boolean;
  /** The name the API sorts this column by; the header becomes a button. */
  sortKey?: string;
  width?: string;
  /** The row's main thing: set darker and heavier so the eye lands on it first. */
  primary?: boolean;
  /** Plain text of the cell. When given, long text is cut with an ellipsis and the whole of it shows on hover. */
  title?: (row: T) => string;
  /** How wide a cut cell may grow (a CSS length). */
  maxWidth?: string;
}

/** The sort the API understands: a field name, with a leading minus for descending. */
function parseSort(sort: string): { field: string; descending: boolean } {
  return sort.startsWith("-") ? { field: sort.slice(1), descending: true } : { field: sort, descending: false };
}

export function DataTable<T>({
  columns,
  rows,
  getKey,
  loading,
  error,
  onRetry,
  sort,
  onSort,
  empty,
  caption,
  footer,
  rowHref,
  onRowClick,
}: {
  columns: Column<T>[];
  rows: T[] | undefined;
  getKey: (row: T) => string | number;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  sort?: string;
  onSort?: (sort: string) => void;
  empty: { title: string; hint?: ReactNode; action?: ReactNode };
  caption: string;
  footer?: ReactNode;
  /** Where a row leads. The whole row is then pressable, and an arrow at its end says so. */
  rowHref?: (row: T) => string;
  /** For a row that opens something on the same screen (an editor) rather than another screen. */
  onRowClick?: (row: T) => void;
}) {
  const current = sort ? parseSort(sort) : null;
  const router = useRouter();

  function open(event: MouseEvent<HTMLTableRowElement>, row: T) {
    // A link, button or field inside the row keeps its own job; so does a text selection or a modified click.
    if ((event.target as HTMLElement).closest("a, button, input, select, textarea, label")) return;
    if (window.getSelection()?.toString()) return;
    const href = rowHref?.(row);
    if (href) {
      if (event.metaKey || event.ctrlKey) window.open(href, "_blank");
      else router.push(href);
    } else onRowClick?.(row);
  }
  const pressable = rowHref !== undefined || onRowClick !== undefined;

  return (
    <div className={styles.wrap}>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              {columns.map((column) => {
                const active = current && column.sortKey === current.field;
                const ariaSort = active ? (current.descending ? "descending" : "ascending") : column.sortKey ? "none" : undefined;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={ariaSort}
                    className={[column.numeric ? styles.numeric : "", column.key === "actions" ? styles.actions : ""].filter(Boolean).join(" ") || undefined}
                    style={column.width ? { width: column.width } : undefined}
                    data-noprint={column.key === "actions" ? "" : undefined}
                  >
                    {column.sortKey && onSort ? (
                      <button
                        type="button"
                        className={styles.sortButton}
                        onClick={() => {
                          const key = column.sortKey as string;
                          onSort(active && !current.descending ? `-${key}` : key);
                        }}
                      >
                        {column.header}
                        {active ? (
                          current.descending ? <IconArrowDown size={16} stroke={1.75} aria-hidden /> : <IconArrowUp size={16} stroke={1.75} aria-hidden />
                        ) : (
                          <IconArrowsSort size={16} stroke={1.5} aria-hidden className={styles.sortIdle} />
                        )}
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
              {pressable ? (
                <th scope="col" className={styles.chevronCell} data-noprint>
                  <span className="sr-only">Open</span>
                </th>
              ) : null}
            </tr>
          </thead>
          {loading && !rows ? (
            <SkeletonRows columns={columns.length + (pressable ? 1 : 0)} />
          ) : rows && rows.length > 0 ? (
            <tbody>
              {rows.map((row) => {
                return (
                  <tr key={getKey(row)} className={pressable ? styles.pressable : undefined} onClick={pressable ? (event) => open(event, row) : undefined}>
                    {columns.map((column) => (
                      <td
                        key={column.key}
                        data-noprint={column.key === "actions" ? "" : undefined}
                        className={[column.numeric ? styles.numeric : "", column.primary ? styles.primary : "", column.key === "actions" ? styles.actions : ""].filter(Boolean).join(" ") || undefined}
                      >
                        {column.title ? (
                          <span className={styles.clip} style={{ maxWidth: column.maxWidth ?? "32ch" }} title={column.title(row)}>
                            {column.cell(row)}
                          </span>
                        ) : (
                          column.cell(row)
                        )}
                      </td>
                    ))}
                    {pressable ? (
                      <td className={styles.chevronCell} aria-hidden data-noprint>
                        <IconChevronRight size={18} stroke={1.75} />
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          ) : null}
          {footer && rows && rows.length > 0 ? <tfoot>{footer}</tfoot> : null}
        </table>
      </div>
      {error && !rows ? <ErrorState error={error} onRetry={onRetry} /> : null}
      {!error && rows && rows.length === 0 ? <EmptyState title={empty.title} action={empty.action}>{empty.hint}</EmptyState> : null}
    </div>
  );
}

/** "1 to 25 of 140", with the way to move through the pages. */
export function Pagination({
  total,
  limit,
  offset,
  onOffset,
  noun = "rows",
}: {
  total: number;
  limit: number;
  offset: number;
  onOffset: (offset: number) => void;
  noun?: string;
}) {
  if (total === 0) return null;
  const first = offset + 1;
  const last = Math.min(offset + limit, total);
  return (
    <nav className={styles.pagination} aria-label="Pages" data-noprint>
      <p className="muted">
        {first} to {last} of {total} {noun}
      </p>
      <div className={styles.pageButtons}>
        <Button small icon={<IconChevronLeft size={18} stroke={1.75} aria-hidden />} disabled={offset === 0} onClick={() => onOffset(Math.max(0, offset - limit))} aria-label="Previous page" />
        <Button small icon={<IconChevronRight size={18} stroke={1.75} aria-hidden />} disabled={offset + limit >= total} onClick={() => onOffset(offset + limit)} aria-label="Next page" />
      </div>
    </nav>
  );
}

/** The filters that are on, each removable, with one button to clear them all. */
export function FilterChips({ chips, onRemove, onClear }: { chips: Array<{ key: string; label: string }>; onRemove: (key: string) => void; onClear: () => void }) {
  if (chips.length === 0) return null;
  return (
    <div className={styles.chips} role="group" aria-label="Filters in use" data-noprint>
      {chips.map((chip) => (
        <span key={chip.key} className={styles.chip}>
          {chip.label}
          <button type="button" onClick={() => onRemove(chip.key)} aria-label={`Remove filter ${chip.label}`}>
            <IconX size={12} stroke={2} aria-hidden />
          </button>
        </span>
      ))}
      <button type="button" className={styles.clearAll} onClick={onClear}>
        Clear all
      </button>
    </div>
  );
}
