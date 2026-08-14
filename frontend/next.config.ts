import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // Where this build is served from, which is now two different places.
  //
  // On its own subdomain it sits at the root and the prefix must be empty; on
  // the shop's host it lives under /plumber and every asset and route has to
  // carry that. Read from the environment so one codebase produces both without
  // either deployment being edited into the other.
  basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "/plumber",
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
