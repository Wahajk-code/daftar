"use client";

import { IconPlus } from "@tabler/icons-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, useCallback, useContext, type ReactNode } from "react";
import type { Role } from "@/api/types";
import { ExpenseForm } from "@/components/documents/ExpenseForm";
import { InviteForm } from "./InviteForm";
import { PurchaseForm } from "@/components/documents/PurchaseForm";
import { VoucherForm } from "@/components/documents/VoucherForm";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import styles from "./CreateModal.module.css";

export type CreateKind = "expense" | "purchase" | "voucher" | "invite";

const WHO_CAN: Record<CreateKind, readonly Role[]> = {
  expense: ["admin", "accountant", "staff"],
  purchase: ["admin", "accountant"],
  voucher: ["admin", "accountant"],
  invite: ["admin"],
};

const COPY: Record<CreateKind, { title: string; description: string }> = {
  expense: { title: "New expense", description: "Save it as a draft, then send it for approval when it is ready." },
  purchase: { title: "New purchase", description: "The server works out the tax as you type; nothing here is trusted from the browser." },
  voucher: { title: "New voucher", description: "Debits must equal credits before it can be saved." },
  invite: { title: "Invite someone", description: "They get an email with a link to set their name and password." },
};

interface CreateApi {
  /** Opens the form for a new document over the current screen. */
  open: (kind: CreateKind) => void;
  /** What this person may start. */
  allowed: CreateKind[];
}

const CreateContext = createContext<CreateApi | null>(null);

export function useCreate(): CreateApi {
  const api = useContext(CreateContext);
  if (!api) throw new Error("useCreate is only available inside the signed-in app");
  return api;
}

const isKind = (value: string | null): value is CreateKind =>
  value === "expense" || value === "purchase" || value === "voucher" || value === "invite";

/**
 * New documents are written in a modal over whatever screen the person is on, with the page behind it softly blurred. The
 * modal is driven by the address (`?new=expense`), so the back button closes it and a copied link opens it.
 */
export function CreateProvider({ role, children }: { role: Role; children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const allowed = (Object.keys(WHO_CAN) as CreateKind[]).filter((kind) => WHO_CAN[kind].includes(role));

  const requested = params.get("new");
  const kind = isKind(requested) && allowed.includes(requested) ? requested : null;

  const withParam = useCallback(
    (value: CreateKind | null) => {
      const next = new URLSearchParams(params.toString());
      if (value) next.set("new", value);
      else next.delete("new");
      const query = next.toString();
      return query ? `${pathname}?${query}` : pathname;
    },
    [params, pathname],
  );

  const open = useCallback((value: CreateKind) => router.push(withParam(value), { scroll: false }), [router, withParam]);
  const close = useCallback(() => router.replace(withParam(null), { scroll: false }), [router, withParam]);

  return (
    <CreateContext.Provider value={{ open, allowed }}>
      {children}
      <Dialog open={kind !== null} onClose={close} size={kind === "invite" ? "sm" : "xl"} title={kind ? COPY[kind].title : ""} description={kind ? COPY[kind].description : undefined}>
        <div className={styles.modalForm}>
          {kind === "expense" ? <ExpenseForm onClose={close} /> : null}
          {kind === "purchase" ? <PurchaseForm onClose={close} /> : null}
          {kind === "voucher" ? <VoucherForm onClose={close} /> : null}
          {kind === "invite" ? <InviteForm onClose={close} /> : null}
        </div>
      </Dialog>
    </CreateContext.Provider>
  );
}

/** A button that starts a new document in the modal. It is not drawn for a role that may not write that kind. */
export function NewDocumentButton({ kind, children, primary = true }: { kind: CreateKind; children: ReactNode; primary?: boolean }) {
  const create = useCreate();
  if (!create.allowed.includes(kind)) return null;
  return (
    <Button variant={primary ? "primary" : "secondary"} icon={<IconPlus size={20} stroke={2} aria-hidden />} onClick={() => create.open(kind)}>
      {children}
    </Button>
  );
}
