"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/api/client";
import { ApiError, messageFor } from "@/api/errors";
import { useAccounts, useAction } from "@/api/queries";
import type { AccountingSettings, Account, PostingAccount } from "@/api/types";
import { useMe } from "@/components/shell/MeContext";
import { Button } from "@/components/ui/Button";
import { SelectField } from "@/components/ui/Field";
import { Instant } from "@/components/ui/Format";
import { PageHeader, Panel } from "@/components/ui/Layout";
import { Banner, ErrorState, LoadingBlock } from "@/components/ui/States";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const KEYS: Array<{ key: PostingAccount["key"]; label: string; about: string; type: Account["type"] }> = [
  { key: "cash", label: "Cash", about: "Paid in cash: this account is credited.", type: "asset" },
  { key: "bank", label: "Bank", about: "Paid by bank transfer, card or cheque: this account is credited.", type: "asset" },
  { key: "input_sales_tax", label: "Sales tax paid on purchases", about: "The sales tax a vendor charged, debited here.", type: "asset" },
  { key: "sales_tax_withheld", label: "Sales tax withheld from vendors", about: "Credited with sales tax kept back from a vendor's payment.", type: "liability" },
  { key: "income_tax_withheld", label: "Income tax withheld from vendors", about: "Credited with income tax kept back from a vendor's payment.", type: "liability" },
];

function NumberingYear({ canWrite }: { canWrite: boolean }) {
  const settings = useQuery({ queryKey: ["record", "accounting-settings"], queryFn: () => api<AccountingSettings>("/settings/accounting") });
  const [month, setMonth] = useState<string | null>(null);
  const save = useAction<void, AccountingSettings>({
    mutationFn: () => api<AccountingSettings>("/settings/accounting", { method: "PUT", body: { fiscal_year_start_month: Number(month) } }),
    success: "Numbering year saved",
    invalidate: [["record", "accounting-settings"]],
    onSuccess: () => setMonth(null),
  });
  if (settings.isPending) return <LoadingBlock label="Loading the settings" />;
  if (settings.error) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;
  const chosen = month ?? String(settings.data.fiscal_year_start_month);
  const changed = chosen !== String(settings.data.fiscal_year_start_month);
  const error = save.error instanceof ApiError ? save.error : null;
  return (
    <Panel title="When the numbering year starts" id="numbering">
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", maxWidth: 620 }}>
        <p>
          Voucher numbers read like <span className="mono">PV-2026-0007</span>: the type, the year, and a running number with no gaps. The year follows the date on the voucher.
          Choose January for the calendar year, or the month your financial year starts in; the year is then named by the year it ends in
          (a July start makes 1 July 2026 part of year 2027).
        </p>
        <SelectField
          label="Numbering year starts in"
          value={chosen}
          onChange={(event) => setMonth(event.target.value)}
          options={MONTHS.map((name, index) => ({ value: index + 1, label: name }))}
          disabled={!canWrite}
          hint={`A voucher dated today would be numbered in year ${settings.data.numbering_year_today}.`}
        />
        {changed ? (
          <Banner tone="caution" title="This affects vouchers posted from now on">
            Numbers already given never change. A different year start begins a new count for any year label it creates, so the same year can end up with
            a part-year count. Change it at the start of a financial year if you can.
          </Banner>
        ) : null}
        {error && error.fields.length === 0 ? <Banner tone="negative" title="Could not save">{messageFor(error)}</Banner> : null}
        {canWrite ? (
          <div>
            <Button variant="primary" pending={save.isPending} disabled={!changed} onClick={() => save.mutate()}>
              Save numbering year
            </Button>
          </div>
        ) : null}
        <p className="faint">Last changed <Instant value={settings.data.updated_at} />.</p>
      </div>
    </Panel>
  );
}

function PostingAccounts({ canWrite }: { canWrite: boolean }) {
  const accounts = useAccounts();
  const rows = useQuery({ queryKey: ["record", "posting-accounts"], queryFn: () => api<PostingAccount[]>("/posting-accounts") });
  const [draft, setDraft] = useState<Record<string, string>>({});
  const save = useAction<{ key: string; accountId: number }, PostingAccount>({
    mutationFn: ({ key, accountId }) => api<PostingAccount>(`/posting-accounts/${key}`, { method: "PUT", body: { account_id: accountId } }),
    success: "Posting account saved",
    invalidate: [["record", "posting-accounts"]],
    onSuccess: (_, { key }) => setDraft((current) => { const next = { ...current }; delete next[key]; return next; }),
  });
  if (rows.isPending || accounts.isPending) return <LoadingBlock label="Loading the posting accounts" />;
  const failure = rows.error ?? accounts.error;
  if (failure) return <ErrorState error={failure} onRetry={() => { rows.refetch(); accounts.refetch(); }} />;
  const current = new Map((rows.data ?? []).map((row) => [row.key, row.account_id]));
  return (
    <Panel title="Where generated vouchers post" id="posting">
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <p className="muted">When a voucher is made from an approved expense or purchase, these accounts are used for the payment and the taxes. The expense itself goes to the account of its category.</p>
        {KEYS.map(({ key, label, about, type }) => {
          const options = (accounts.data ?? []).filter((account) => account.is_postable && account.type === type).map((account) => ({ value: account.id, label: `${account.code} ${account.name}` }));
          const value = draft[key] ?? (current.has(key) ? String(current.get(key)) : "");
          const changed = value !== "" && value !== String(current.get(key) ?? "");
          return (
            <div key={key} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "var(--space-3)", alignItems: "end" }}>
              <SelectField label={label} hint={about} value={value} placeholder="Not set" onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} options={options} disabled={!canWrite} />
              {canWrite ? (
                <Button pending={save.isPending && save.variables?.key === key} disabled={!changed} onClick={() => save.mutate({ key, accountId: Number(value) })}>
                  Save
                </Button>
              ) : null}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

export function Settings() {
  const me = useMe();
  const canWrite = me.role === "admin" || me.role === "accountant";
  return (
    <>
      <PageHeader title="Accounting settings" description="Choices that apply to the whole company. The Accountant in charge decides them." />
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <NumberingYear canWrite={canWrite} />
        <PostingAccounts canWrite={canWrite} />
      </div>
    </>
  );
}
