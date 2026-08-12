import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // Served from /plumber on the same host as the shop, so every asset and
  // route has to carry the prefix. The API is reached at /plumber-api, which
  // nginx forwards to this system's own backend on the other server.
  basePath: "/plumber",
  images: {
    unoptimized: true,
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
    ],
  },
};

export default nextConfig;
