"use client";

import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import { ZERO_PAISA, isAmount, stripSeparators, toPaisa } from "@/lib/money";
import { Select } from "./Select";
import styles from "./Field.module.css";

interface Shell {
  label: string;
  hint?: ReactNode;
  error?: string;
  required?: boolean;
  /** Hide the label visually (it is still read out) when a table header or a heading already names the field. */
  hideLabel?: boolean;
  className?: string;
}

function join(...names: Array<string | undefined | false>) {
  return names.filter(Boolean).join(" ");
}

/** The label, the control and the message under it, tied together so a screen reader reads them as one. */
function FieldShell({
  label,
  hint,
  error,
  required,
  hideLabel,
  className,
  children,
}: Shell & { children: (props: { id: string; "aria-describedby"?: string; "aria-invalid"?: true; "aria-required"?: true }) => ReactNode }) {
  const id = useId();
  const messageId = `${id}-message`;
  const describedBy = error || hint ? messageId : undefined;
  return (
    <div className={join(styles.field, className)}>
      <label htmlFor={id} className={join(styles.label, hideLabel && "sr-only")}>
        {label}
        {required ? <span className={styles.required} aria-hidden> *</span> : null}
      </label>
      {children({
        id,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
        "aria-required": required ? true : undefined,
      })}
      {error ? (
        <p id={messageId} className={styles.error} role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export const TextField = forwardRef<HTMLInputElement, Shell & Omit<InputHTMLAttributes<HTMLInputElement>, "className">>(
  function TextField({ label, hint, error, required, hideLabel, className, ...input }, ref) {
    return (
      <FieldShell {...{ label, hint, error, required, hideLabel, className }}>
        {(aria) => <input ref={ref} className={`${styles.control} user-text`} {...aria} {...input} />}
      </FieldShell>
    );
  },
);

export const TextAreaField = forwardRef<HTMLTextAreaElement, Shell & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className">>(
  function TextAreaField({ label, hint, error, required, hideLabel, className, ...input }, ref) {
    return (
      <FieldShell {...{ label, hint, error, required, hideLabel, className }}>
        {(aria) => <textarea ref={ref} rows={3} className={`${styles.control} ${styles.area} user-text`} {...aria} {...input} />}
      </FieldShell>
    );
  },
);

export interface Option {
  value: string | number;
  label: string;
  disabled?: boolean;
}

/** What a choice reports: the same shape a native field gives, so callers read `event.target.value`. */
export interface SelectChange {
  target: { value: string };
}

/** A labelled drop-down, drawn by the app (see Select) so it matches every other field. */
export const SelectField = forwardRef<
  HTMLButtonElement,
  Shell & { options: Option[]; placeholder?: string; value: string | number; onChange?: (event: SelectChange) => void; disabled?: boolean }
>(function SelectField({ label, hint, error, required, hideLabel, className, options, placeholder, value, onChange, disabled }, ref) {
  return (
    <FieldShell {...{ label, hint, error, required, hideLabel, className }}>
      {(aria) => (
        <Select ref={ref} {...aria} value={String(value)} options={options} placeholder={placeholder} disabled={disabled} onChange={(next) => onChange?.({ target: { value: next } })} />
      )}
    </FieldShell>
  );
});

/**
 * An amount box. It accepts what a person types (commas and spaces are dropped), keeps the value as plain amount text and
 * never turns it into a number. `onValue` gets the cleaned text; whether it is a valid amount is shown as the person leaves.
 */
export function MoneyField({
  label,
  hint,
  error,
  required,
  hideLabel,
  className,
  value,
  onValue,
  ...input
}: Shell &
  Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "value" | "onChange" | "type"> & {
    value: string;
    onValue: (text: string) => void;
  }) {
  return (
    <FieldShell {...{ label, hint, error, required, hideLabel, className }}>
      {(aria) => (
        <input
          className={join(styles.control, styles.money, "num")}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(event) => onValue(event.target.value)}
          onBlur={(event) => {
            const clean = stripSeparators(event.target.value);
            if (clean !== event.target.value) onValue(clean);
            input.onBlur?.(event);
          }}
          {...aria}
          {...input}
        />
      )}
    </FieldShell>
  );
}

/** Why an amount is not acceptable, or undefined when it is fine or empty. */
export function amountProblem(text: string, { allowZero = false }: { allowZero?: boolean } = {}): string | undefined {
  const clean = stripSeparators(text);
  if (clean === "") return undefined;
  if (!isAmount(clean)) return "Enter an amount with at most two decimal places, such as 1500.00.";
  if (!allowZero && toPaisa(clean) === ZERO_PAISA) return "The amount must be more than zero.";
  return undefined;
}

export function CheckboxField({
  label,
  hint,
  className,
  ...input
}: { label: string; hint?: ReactNode; className?: string } & Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "className">) {
  const id = useId();
  return (
    <div className={join(styles.check, className)}>
      <input id={id} type="checkbox" {...input} />
      <label htmlFor={id}>
        {label}
        {hint ? <span className={styles.hint}> {hint}</span> : null}
      </label>
    </div>
  );
}
