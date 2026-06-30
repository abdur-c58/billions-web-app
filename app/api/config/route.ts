import { NextResponse } from "next/server";
import {
  getEffectiveBackendUrl,
  probeBackendHealth,
  readStoredBackendTunnel,
} from "@/lib/backend-tunnel";

/** Expose client-safe runtime config (tunnel URL for large uploads, etc.). */
export async function GET() {
  const stored = await readStoredBackendTunnel();
  const backendUrl = await getEffectiveBackendUrl();
  const source = stored?.backend_url
    ? "r2"
    : process.env.BROLL_BACKEND_URL
      ? "env"
      : process.env.VERCEL
        ? null
        : "local";

  let health: { ok: boolean; status: number | null; error: string | null } | null = null;
  if (backendUrl) {
    health = await probeBackendHealth(backendUrl);
  }

  return NextResponse.json({
    backend_url: backendUrl,
    audio_upload_url: backendUrl ? `${backendUrl}/api/project/upload/audio` : null,
    tunnel_source: source,
    tunnel_updated_at: stored?.updated_at ?? null,
    backend_reachable: health?.ok ?? null,
    backend_health_error: health?.error ?? null,
  });
}
