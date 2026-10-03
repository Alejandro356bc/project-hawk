import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  basePath: "/quorum",
  async redirects() {
    return [
      {
        source: "/",
        destination: "/quorum",
        basePath: false,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
