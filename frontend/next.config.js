/** @type {import('next').NextConfig} */
const backendUrl = (
  process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || ""
).trim();
const apiBase = (backendUrl || "http://localhost:8000").replace(/\/+$/, "");

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
