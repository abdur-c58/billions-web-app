import { NextResponse } from "next/server";
import {
  getEffectiveBackendUrl,
  probeBackendHealth,
  readStoredBackendTunnel,
} from "@/lib/backend-tunnel";

export async function GET() {
  const stored = await readStoredBackendTunnel();
  const backendUrl = await getEffectiveBackendUrl();
  const backendUrlEnv = process.env.BROLL_BACKEND_URL?.replace(/\/$/, "") || null;
  const publicBackendUrl =
    process.env.NEXT_PUBLIC_BROLL_BACKEND_URL?.replace(/\/$/, "") || null;
  const port = process.env.BROLL_BACKEND_PORT || "8766";

  let backendReachable: boolean | null = null;
  let backendHealthStatus: number | null = null;
  let backendHealthError: string | null = null;

  if (backendUrl) {
    const health = await probeBackendHealth(backendUrl);
    backendReachable = health.ok;
    backendHealthStatus = health.status;
    backendHealthError = health.error;
  }

  return NextResponse.json({
    temporary_debug: true,
    vercel: Boolean(process.env.VERCEL),
    vercel_url: process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null,
    env: {
      BROLL_BACKEND_URL: backendUrlEnv,
      BROLL_BACKEND_PORT: port,
      effective_backend_url: backendUrl,
      stored_tunnel_url: stored?.backend_url ?? null,
      tunnel_updated_at: stored?.updated_at ?? null,
      NEXT_PUBLIC_BROLL_BACKEND_URL: publicBackendUrl,
      NEXT_PUBLIC_BROLL_BACKEND_PORT: process.env.NEXT_PUBLIC_BROLL_BACKEND_PORT || "8766",
      audio_upload_url: backendUrl ? `${backendUrl}/api/project/upload/audio` : null,
    },
    backend_reachable: backendReachable,
    backend_health_status: backendHealthStatus,
    backend_health_error: backendHealthError,
  });
}
