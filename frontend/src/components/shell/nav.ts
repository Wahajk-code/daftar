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
      { href: "/", label: "Home", icon: IconLayoutDashboard, roles: EVERYONE },
      { href: "/approvals", label: "Approvals", icon: IconChecklist, roles: ["admin", "approver"] },
    ],
  },
  {
    heading: "Work",
    items: [
      { href: "/expenses", label: "Expenses", icon: IconReceipt2, roles: EVERYONE },
      { href: "/purchases", label: "Purchases", icon: IconShoppingBag, roles: OFFICE },
      { href: "/vouchers", label: "Vouchers", icon: IconNotebook, roles: OFFICE },
      { href: "/reports", label: "Reports", icon: IconChartBar, roles: OFFICE },
    ],
  },
  {
    heading: "Setup",
    items: [
      { href: "/vendors", label: "Vendors", icon: IconBuildingStore, roles: OFFICE },
      { href: "/accounts", label: "Chart of accounts", icon: IconListTree, roles: OFFICE },
      { href: "/categories", label: "Categories", icon: IconTags, roles: OFFICE },
      { href: "/cost-centers", label: "Cost centres", icon: IconSitemap, roles: OFFICE },
      { href: "/projects", label: "Projects", icon: IconBriefcase, roles: OFFICE },
      { href: "/tax-rules", label: "Tax rates", icon: IconPercentage, roles: OFFICE },
      { href: "/periods", label: "Periods", icon: IconCalendarStats, roles: OFFICE },
      { href: "/settings", label: "Accounting settings", icon: IconSettings, roles: OFFICE },
    ],
  },
  {
    heading: "People",
    items: [
      { href: "/users", label: "Users and invites", icon: IconUsers, roles: ["admin"] },
      { href: "/audit", label: "Audit log", icon: IconHistory, roles: ["admin"] },
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
