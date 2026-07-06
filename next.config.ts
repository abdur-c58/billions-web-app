import type { NextConfig } from "next";

const backendPort = process.env.BROLL_BACKEND_PORT || "8766";
// When deployed (Vercel), set BROLL_BACKEND_URL to your Cloudflare Tunnel URL,
// e.g. https://backend.yourdomain.com — no trailing slash.
// Locally this falls back to http://127.0.0.1:<port>.
const backendBase =
  process.env.BROLL_BACKEND_URL?.replace(/\/$/, "") ||
  `http://127.0.0.1:${backendPort}`;

const nextConfig: NextConfig = {
  experimental: {
    // Project audio uploads are proxied to the Python backend via rewrites.
    // Long narration MP3s (2h+) can exceed 100MB.
    proxyClientMaxBodySize: "500mb",
  },
  async rewrites() {
    return [
      {
        source: "/api/whisper/hardware",
        destination: `${backendBase}/api/whisper/hardware`,
      },
      {
        source: "/api/project/:path*",
        destination: `${backendBase}/api/project/:path*`,
      },
      {
        source: "/api/segments",
        destination: `${backendBase}/api/segments`,
      },
      {
        source: "/api/health",
        destination: `${backendBase}/api/health`,
      },
      {
        source: "/api/fetch",
        destination: `${backendBase}/api/fetch`,
      },
      {
        source: "/api/search",
        destination: `${backendBase}/api/search`,
      },
      {
        source: "/api/select/:path*",
        destination: `${backendBase}/api/select/:path*`,
      },
      {
        source: "/api/select",
        destination: `${backendBase}/api/select`,
      },
      {
        source: "/api/audio/:path*",
        destination: `${backendBase}/api/audio/:path*`,
      },
      {
        source: "/api/export/:path*",
        destination: `${backendBase}/api/export/:path*`,
      },
      {
        source: "/api/activity",
        destination: `${backendBase}/api/activity`,
      },
      {
        source: "/api/duplicates",
        destination: `${backendBase}/api/duplicates`,
      },
      {
        source: "/api/flagged/:path*",
        destination: `${backendBase}/api/flagged/:path*`,
      },
      {
        source: "/api/rescore/:path*",
        destination: `${backendBase}/api/rescore/:path*`,
      },
      {
        source: "/api/folder-fetch/:path*",
        destination: `${backendBase}/api/folder-fetch/:path*`,
      },
      {
        source: "/api/remotion/:path*",
        destination: `${backendBase}/api/remotion/:path*`,
      },
    ];
  },
};

export default nextConfig;
