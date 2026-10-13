import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // File events do not cross a Windows bind mount into the container, so the dev server polls.
  // Set only in development; it is costly and not needed in a production build.
  ...(process.env.NODE_ENV === "development" ? { watchOptions: { pollIntervalMs: 1000 } } : {}),
  // Headers on every response. No Content-Security-Policy: Next.js needs per-request nonces for one, which is a later step.
  // The camera is allowed for this site only (the receipt photo button); everything else a page could ask for is off.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(), payment=()" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
    ];
  },
};

export default nextConfig;
