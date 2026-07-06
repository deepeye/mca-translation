import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // prod 经公网网关 /mca 子路径挂载;dev 留空(NEXT_PUBLIC_BASE_PATH 未注入)。
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || undefined,
};

export default nextConfig;
