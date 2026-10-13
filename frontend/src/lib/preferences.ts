"use client";

/**
 * Preferences that belong to the browser, not the account: theme, density and whether the sidebar is folded. They are kept
 * in plain cookies so the server can render the right look on the first byte. None of them is a secret.
 */
export type Theme = "system" | "light" | "dark";
export type Density = "compact" | "comfortable";

const YEAR = 60 * 60 * 24 * 365;

function write(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/; max-age=${YEAR}; SameSite=Strict`;
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  write("daftar_theme", theme);
}

export function applyDensity(density: Density) {
  document.documentElement.setAttribute("data-density", density);
  write("daftar_density", density);
}

export function applySidebar(collapsed: boolean) {
  document.documentElement.setAttribute("data-sidebar", collapsed ? "collapsed" : "expanded");
  write("daftar_sidebar", collapsed ? "collapsed" : "expanded");
}

export function currentTheme(): Theme {
  const value = document.documentElement.getAttribute("data-theme");
  return value === "light" || value === "dark" ? value : "system";
}

export function currentDensity(): Density {
  return document.documentElement.getAttribute("data-density") === "comfortable" ? "comfortable" : "compact";
}
