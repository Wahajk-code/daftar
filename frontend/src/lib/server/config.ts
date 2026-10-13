/** Server-side settings, read from the environment. Nothing here is sent to the browser. */

export const ACCESS_COOKIE = "daftar_at";
export const REFRESH_COOKIE = "daftar_rt";

/** Preference cookies. They hold no secret, so the page can render with the right theme and sidebar on the first byte. */
export const THEME_COOKIE = "daftar_theme";
export const DENSITY_COOKIE = "daftar_density";
export const SIDEBAR_COOKIE = "daftar_sidebar";

export const REFRESH_MAX_AGE_SECONDS = 7 * 24 * 60 * 60; // matches the API's REFRESH_TOKEN_TTL_DAYS

export const serverConfig = {
  /** Where the API lives, as seen from this server. */
  apiBase: (process.env.API_BASE_URL ?? "http://localhost:8001").replace(/\/$/, ""),
  /** Proves to the API that a forwarded client address really comes from this server. */
  bffSecret: process.env.BFF_SHARED_SECRET ?? "",
  /** Shows the demonstration accounts under the sign-in form. */
  demoMode: process.env.DEMO_MODE === "true",
  secureCookies: process.env.NODE_ENV === "production",
};

export const BFF_SECRET_HEADER = "X-Daftar-BFF-Secret";
export const BFF_CLIENT_IP_HEADER = "X-Daftar-Client-Ip";
