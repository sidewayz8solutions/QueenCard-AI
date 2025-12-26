import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Avoid React 18 dev double-invocation of effects which can cause loops with HMR
  reactStrictMode: false,
};

export default nextConfig;
