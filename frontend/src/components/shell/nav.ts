import {
  IconBriefcase,
  IconBuildingStore,
  IconCalendarStats,
  IconChartBar,
  IconChecklist,
  IconHistory,
  IconLayoutDashboard,
  IconListTree,
  IconNotebook,
  IconPercentage,
  IconReceipt2,
  IconSettings,
  IconShoppingBag,
  IconSitemap,
  IconTags,
  IconUsers,
  type Icon,
} from "@tabler/icons-react";
import type { Role } from "@/api/types";

export interface NavItem {
  href: string;
  label: string;
  /** One line for the Help center. */
  hint: string;
  icon: Icon;
  roles: readonly Role[];
  /** Extra path prefixes that also mark this item as the current place. */
  also?: readonly string[];
}

export interface NavGroup {
  heading?: string;
  items: NavItem[];
}

const EVERYONE: readonly Role[] = ["admin", "accountant", "approver", "staff"];
const OFFICE: readonly Role[] = ["admin", "accountant", "approver"];

/** The sidebar. Each person sees the entries their role may open; the API still checks every call. */
export const NAV: NavGroup[] = [
  {
    items: [
      { href: "/", hint: "What is waiting for you, and this month at a glance", label: "Home", icon: IconLayoutDashboard, roles: EVERYONE },
      { href: "/approvals", hint: "Documents sent for your decision", label: "Approvals", icon: IconChecklist, roles: ["admin", "approver"] },
    ],
  },
  {
    heading: "Work",
    items: [
      { href: "/expenses", hint: "Money spent, with receipts and cost centres", label: "Expenses", icon: IconReceipt2, roles: EVERYONE },
      { href: "/purchases", hint: "Vendor invoices with lines and tax", label: "Purchases", icon: IconShoppingBag, roles: OFFICE },
      { href: "/vouchers", hint: "Debits and credits, numbered when posted", label: "Vouchers", icon: IconNotebook, roles: OFFICE },
      { href: "/reports", hint: "Totals and registers, with CSV download", label: "Reports", icon: IconChartBar, roles: OFFICE },
    ],
  },
  {
    heading: "Setup",
    items: [
      { href: "/vendors", hint: "Who you buy from", label: "Vendors", icon: IconBuildingStore, roles: OFFICE },
      { href: "/accounts", hint: "The accounts vouchers post to", label: "Chart of accounts", icon: IconListTree, roles: OFFICE },
      { href: "/categories", hint: "What an expense is for", label: "Categories", icon: IconTags, roles: OFFICE },
      { href: "/cost-centers", hint: "Where costs are charged", label: "Cost centres", icon: IconSitemap, roles: OFFICE },
      { href: "/projects", hint: "Work that costs are tied to", label: "Projects", icon: IconBriefcase, roles: OFFICE },
      { href: "/tax-rules", hint: "Sales tax and withholding rates", label: "Tax rates", icon: IconPercentage, roles: OFFICE },
      { href: "/periods", hint: "Close a month so it cannot change", label: "Periods", icon: IconCalendarStats, roles: OFFICE },
      { href: "/settings", hint: "Voucher numbering and posting accounts", label: "Accounting settings", icon: IconSettings, roles: OFFICE },
    ],
  },
  {
    heading: "People",
    items: [
      { href: "/users", hint: "Invite people and set their roles", label: "Users and invites", icon: IconUsers, roles: ["admin"] },
      { href: "/audit", hint: "Who changed what, and when", label: "Audit log", icon: IconHistory, roles: ["admin"] },
    ],
  },
];

export function navFor(role: Role): NavGroup[] {
  return NAV.map((group) => ({ ...group, items: group.items.filter((item) => item.roles.includes(role)) })).filter(
    (group) => group.items.length > 0,
  );
}

export function isCurrent(pathname: string, item: NavItem): boolean {
  if (item.href === "/") return pathname === "/";
  return [item.href, ...(item.also ?? [])].some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
