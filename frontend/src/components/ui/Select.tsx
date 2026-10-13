"use client";

import { IconCheck, IconChevronDown, IconSearch } from "@tabler/icons-react";
import { forwardRef, useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import styles from "./Select.module.css";

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  /** Text for "nothing chosen". When given, it is also the first choice in the list, so the value can be cleared. */
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  /** `field` is a box like the other fields; `cell` is a borderless cell for a grid of lines. */
  variant?: "field" | "cell";
  className?: string;
  "aria-label"?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
  "aria-required"?: boolean;
}

interface Place {
  left: number;
  width: number;
  top?: number;
  bottom?: number;
  maxHeight: number;
}

/**
 * A drop-down drawn by the app, so the closed box and the open list look like every other control instead of the browser's.
 * It follows the listbox pattern: the button keeps focus, the arrow keys move through the choices, Enter or Space chooses,
 * Escape closes (without closing a dialog around it), and typing a few letters jumps to a choice. The list is placed with
 * fixed coordinates, so a table or a dialog never clips it.
 */
export const Select = forwardRef<HTMLButtonElement, SelectProps>(function Select(
  { value, options, onChange, placeholder, disabled, id, variant = "field", className, ...aria },
  ref,
) {
  const listId = useId();
  const button = useRef<HTMLButtonElement | null>(null);
  const list = useRef<HTMLUListElement>(null);
  const typed = useRef({ text: "", at: 0 });
  const [place, setPlace] = useState<Place | null>(null);
  const [active, setActive] = useState(0);
  const [query, setQuery] = useState("");

  const choices = useMemo<SelectOption[]>(() => (placeholder !== undefined ? [{ value: "", label: placeholder }, ...options] : options), [placeholder, options]);
  const selected = choices.find((choice) => String(choice.value) === value);
  const open = place !== null;

  // A long list gets a search box. Every word typed has to be found in a choice, in any order, so each word narrows it.
  const searchable = choices.length > 8;
  const visible = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    return choices.map((choice, index) => ({ choice, index })).filter(({ choice }) => words.every((word) => choice.label.toLowerCase().includes(word)));
  }, [choices, query]);

  const close = useCallback(() => {
    setPlace(null);
    setQuery("");
  }, []);

  const show = useCallback(() => {
    const trigger = button.current;
    if (!trigger || disabled) return;
    const rect = trigger.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom - 16;
    const above = rect.top - 16;
    const flip = below < 200 && above > below;
    const width = Math.max(rect.width, 220);
    setPlace({
      left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
      width,
      ...(flip ? { bottom: window.innerHeight - rect.top + 6 } : { top: rect.bottom + 6 }),
      maxHeight: Math.max(160, Math.min(340, flip ? above : below)),
    });
    setQuery("");
    const at = choices.findIndex((choice) => String(choice.value) === value);
    setActive(at >= 0 ? at : Math.max(0, choices.findIndex((choice) => !choice.disabled)));
  }, [choices, disabled, value]);

  const choose = useCallback(
    (index: number) => {
      const choice = choices[index];
      if (!choice || choice.disabled) return;
      onChange(String(choice.value));
      close();
      button.current?.focus();
    },
    [choices, onChange, close],
  );

  // Close on a press elsewhere, on a resize, and when something other than the list scrolls under it.
  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!list.current?.contains(target) && !button.current?.contains(target)) close();
    };
    const onScroll = (event: Event) => {
      if (!list.current?.contains(event.target as Node)) close();
    };
    document.addEventListener("pointerdown", onPointer);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, close]);

  // Keep the highlighted choice in view as the arrow keys move.
  useEffect(() => {
    if (open) list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  function step(from: number, direction: 1 | -1): number {
    const shown = visible.filter(({ choice }) => !choice.disabled).map(({ index }) => index);
    if (shown.length === 0) return from;
    const here = shown.indexOf(from);
    if (here < 0) return direction === 1 ? shown[0] : shown[shown.length - 1];
    return shown[Math.max(0, Math.min(shown.length - 1, here + direction))];
  }

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (disabled) return;
    const { key } = event;
    const inSearch = event.target instanceof HTMLInputElement;
    if (!open) {
      if (key === "ArrowDown" || key === "ArrowUp" || key === "Enter" || key === " ") {
        event.preventDefault();
        show();
      }
      return;
    }
    if (key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close();
    } else if (key === "ArrowDown") {
      event.preventDefault();
      setActive((current) => step(current, 1));
    } else if (key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => step(current, -1));
    } else if (key === "Home" && !inSearch) {
      event.preventDefault();
      setActive(step(-1, 1));
    } else if (key === "End" && !inSearch) {
      event.preventDefault();
      setActive(step(choices.length, -1));
    } else if (key === "Enter" || (key === " " && !inSearch)) {
      event.preventDefault();
      choose(active);
    } else if (key === "Tab") {
      close();
    } else if (!inSearch && !searchable && key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      // Typing a few letters jumps to the first choice that starts with them.
      const now = Date.now();
      typed.current = { text: (now - typed.current.at > 700 ? "" : typed.current.text) + key.toLowerCase(), at: now };
      const found = choices.findIndex((choice) => !choice.disabled && choice.label.toLowerCase().startsWith(typed.current.text));
      if (found >= 0) setActive(found);
    }
  }

  return (
    <>
      <button
        {...aria}
        ref={(element) => {
          button.current = element;
          if (typeof ref === "function") ref(element);
          else if (ref) ref.current = element;
        }}
        id={id}
        type="button"
        role="combobox"
        className={`${styles.trigger} ${variant === "cell" ? styles.cell : ""} ${className ?? ""}`}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        onClick={() => (open ? close() : show())}
        onKeyDown={onKeyDown}
      >
        <span className={`${styles.value} ${selected && selected.value !== "" ? "" : styles.placeholder} clip`}>{selected ? selected.label : (placeholder ?? "")}</span>
        <IconChevronDown size={18} stroke={1.75} aria-hidden className={`${styles.chevron} ${open ? styles.flipped : ""}`} />
      </button>
      {open ? (
        <ul
          ref={list}
          id={listId}
          role="listbox"
          tabIndex={-1}
          aria-label={aria["aria-label"]}
          className={styles.list}
          style={{ left: place.left, width: place.width, top: place.top, bottom: place.bottom, maxHeight: place.maxHeight }}
          onMouseDown={(event) => event.target instanceof HTMLInputElement || event.preventDefault()}
          onKeyDown={onKeyDown}
        >
          {searchable ? (
            <li role="presentation" className={styles.search}>
              <IconSearch size={18} stroke={1.5} aria-hidden />
              <input
                autoFocus
                type="search"
                value={query}
                placeholder="Type words to narrow the list"
                aria-label="Narrow the list"
                onChange={(event) => {
                  setQuery(event.target.value);
                  const words = event.target.value.toLowerCase().split(/\s+/).filter(Boolean);
                  const first = choices.findIndex((choice) => !choice.disabled && words.every((word) => choice.label.toLowerCase().includes(word)));
                  setActive(first >= 0 ? first : 0);
                }}
              />
            </li>
          ) : null}
          {visible.length === 0 ? (
            <li role="presentation" className={styles.none}>
              Nothing matches. Remove a word to widen the list.
            </li>
          ) : null}
          {visible.map(({ choice, index }) => {
            const isSelected = String(choice.value) === value;
            return (
              <li
                key={`${choice.value}`}
                id={`${listId}-${index}`}
                role="option"
                data-index={index}
                aria-selected={isSelected}
                aria-disabled={choice.disabled || undefined}
                className={`${styles.option} ${index === active ? styles.active : ""} ${isSelected ? styles.chosen : ""}`}
                onMouseEnter={() => !choice.disabled && setActive(index)}
                onClick={() => choose(index)}
              >
                <span className="clip user-text">{choice.label}</span>
                {isSelected ? <IconCheck size={18} stroke={2} aria-hidden /> : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </>
  );
});
