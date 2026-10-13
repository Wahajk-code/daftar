import type { MetadataRoute } from "next";
import tokens from "../../design/tokens.json";

/**
 * Makes Daftar installable: on a phone, "Add to Home Screen" (or "Install app") puts it on the home screen with its own icon
 * and opens it full screen, like an app. It is the same web app: nothing is stored on the device but the sign-in cookie, and
 * receipts are sent to the server straight away. The colours come from the design tokens.
 */
export default function manifest(): MetadataRoute.Manifest {
  const background = tokens.primitives.gray["150"];
  const ink = tokens.primitives.gray["900"];
  return {
    name: "Daftar",
    short_name: "Daftar",
    description: "Expenses, purchases and vouchers.",
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: background,
    theme_color: ink,
    icons: [
      { src: "/pwa-icons/192", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/pwa-icons/512", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/pwa-icons/maskable", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [{ name: "New expense", short_name: "Expense", description: "Write a new expense", url: "/expenses?new=expense" }],
  };
}
