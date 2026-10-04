import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  basePath: "/hawk",
  turbopack: {
    root: __dirname,
  },
  async redirects() {
    return [
      {
        source: "/",
        destination: "/hawk",
        basePath: false,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
