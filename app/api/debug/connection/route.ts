import { NextResponse } from "next/server";

function backendBaseFromEnv() {
  const port = process.env.BROLL_BACKEND_PORT || "8766";
  return (
    process.env.BROLL_BACKEND_URL?.replace(/\/$/, "") ||
    `http://127.0.0.1:${port}`
  );
}

export async function GET() {
  const port = process.env.BROLL_BACKEND_PORT || "8766";
  const backendUrl = backendBaseFromEnv();
  const backendUrlEnv = process.env.BROLL_BACKEND_URL?.replace(/\/$/, "") || null;
  const publicBackendUrl =
    process.env.NEXT_PUBLIC_BROLL_BACKEND_URL?.replace(/\/$/, "") || null;
  const publicBackendPort = process.env.NEXT_PUBLIC_BROLL_BACKEND_PORT || "8766";

  let backendReachable: boolean | null = null;
  let backendHealthStatus: number | null = null;
  let backendHealthError: string | null = null;

  try {
    const response = await fetch(`${backendUrl}/api/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    backendHealthStatus = response.status;
    backendReachable = response.ok;
  } catch (error) {
    backendReachable = false;
    backendHealthError = error instanceof Error ? error.message : "Health check failed";
  }

  return NextResponse.json({
    temporary_debug: true,
    vercel: Boolean(process.env.VERCEL),
    vercel_url: process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null,
    env: {
      BROLL_BACKEND_URL: backendUrlEnv,
      BROLL_BACKEND_PORT: port,
      effective_backend_url: backendUrl,
      NEXT_PUBLIC_BROLL_BACKEND_URL: publicBackendUrl,
      NEXT_PUBLIC_BROLL_BACKEND_PORT: publicBackendPort,
    },
    backend_reachable: backendReachable,
    backend_health_status: backendHealthStatus,
    backend_health_error: backendHealthError,
  });
}
