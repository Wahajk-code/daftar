import type { MetadataRoute } from "next";

/** Nothing here is for search engines: every screen is private or a sign-in form. */
export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", disallow: "/" } };
}
