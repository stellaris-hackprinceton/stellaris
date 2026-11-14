import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const origin = new URL(process.env.STELLARIS_API_ORIGIN || "http://127.0.0.1:8000");
    if (!["http:", "https:"].includes(origin.protocol)) throw new Error("STELLARIS_API_ORIGIN must use HTTP or HTTPS.");
    return [{ source: "/api/v1/:path*", destination: `${origin.origin}/api/v1/:path*` }];
  },
  cacheComponents: true,
  partialPrefetching: true,
  output: 'standalone',
};

export default nextConfig;
