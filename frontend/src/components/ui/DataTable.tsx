"use client";

import { IconArrowDown, IconArrowUp, IconArrowsSort, IconChevronLeft, IconChevronRight, IconX } from "@tabler/icons-react";
import type { ReactNode } from "react";
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
}) {
  const current = sort ? parseSort(sort) : null;

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
                    className={column.numeric ? styles.numeric : undefined}
                    style={column.width ? { width: column.width } : undefined}
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
                          current.descending ? <IconArrowDown size={14} stroke={1.75} aria-hidden /> : <IconArrowUp size={14} stroke={1.75} aria-hidden />
                        ) : (
                          <IconArrowsSort size={14} stroke={1.5} aria-hidden className={styles.sortIdle} />
                        )}
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          {loading && !rows ? (
            <SkeletonRows columns={columns.length} />
          ) : rows && rows.length > 0 ? (
            <tbody>
              {rows.map((row) => (
                <tr key={getKey(row)}>
                  {columns.map((column) => (
                    <td key={column.key} className={column.numeric ? styles.numeric : undefined}>
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
              ))}
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
    <nav className={styles.pagination} aria-label="Pages">
      <p className="muted">
        {first} to {last} of {total} {noun}
      </p>
      <div className={styles.pageButtons}>
        <Button small icon={<IconChevronLeft size={16} stroke={1.75} aria-hidden />} disabled={offset === 0} onClick={() => onOffset(Math.max(0, offset - limit))} aria-label="Previous page" />
        <Button small icon={<IconChevronRight size={16} stroke={1.75} aria-hidden />} disabled={offset + limit >= total} onClick={() => onOffset(offset + limit)} aria-label="Next page" />
      </div>
    </nav>
  );
}

/** The filters that are on, each removable, with one button to clear them all. */
export function FilterChips({ chips, onRemove, onClear }: { chips: Array<{ key: string; label: string }>; onRemove: (key: string) => void; onClear: () => void }) {
  if (chips.length === 0) return null;
  return (
    <div className={styles.chips} role="group" aria-label="Filters in use">
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
