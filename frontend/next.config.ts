import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // File events do not cross a Windows bind mount into the container, so the dev server polls.
  // Set only in development; it is costly and not needed in a production build.
  ...(process.env.NODE_ENV === "development" ? { watchOptions: { pollIntervalMs: 1000 } } : {}),
};

export default nextConfig;
