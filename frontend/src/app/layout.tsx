import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { Inter, Inter_Tight, Noto_Naskh_Arabic } from "next/font/google";
import { SIDEBAR_COOKIE, THEME_COOKIE } from "@/lib/server/config";
import { Providers } from "./providers";
import "@/styles/tokens.css";
import "@/styles/base.css";

// Inter Tight sets the interface and the headings; Inter, a little wider and more open, sets tables and figures.
const tight = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-tight",
  display: "swap",
});
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});
const naskh = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  weight: ["400", "600"],
  variable: "--font-naskh",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Daftar", template: "%s | Daftar" },
  description: "Expenses, purchases and vouchers.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light dark",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const jar = await cookies();
  const theme = jar.get(THEME_COOKIE)?.value;
  const sidebar = jar.get(SIDEBAR_COOKIE)?.value === "collapsed" ? "collapsed" : "expanded";
  // "System" is the absence of a choice: the stylesheet follows the operating system. Light and Dark are set here, on the
  // server, so the first paint is already right and nothing flashes.
  const dataTheme = theme === "light" || theme === "dark" ? theme : undefined;

  return (
    <html
      lang="en"
      data-theme={dataTheme}
      data-sidebar={sidebar}
      className={`${tight.variable} ${inter.variable} ${naskh.variable}`}
    >
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
