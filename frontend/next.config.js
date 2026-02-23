/** @type {import('next').NextConfig} */
const configuredApiBase = (process.env.NEXT_PUBLIC_API_URL || "").trim();
const apiBase = (configuredApiBase || "http://localhost:8000").replace(/\/+$/, "");

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
