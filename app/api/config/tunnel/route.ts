import { NextResponse } from "next/server";
import {
  normalizeTunnelUrl,
  probeBackendHealth,
  readStoredBackendTunnel,
  writeStoredBackendTunnel,
} from "@/lib/backend-tunnel";

export async function GET() {
  try {
    const stored = await readStoredBackendTunnel();
    if (!stored) {
      return NextResponse.json({ configured: false, backend_url: null });
    }
    const health = await probeBackendHealth(stored.backend_url);
    return NextResponse.json({
      configured: true,
      backend_url: stored.backend_url,
      updated_at: stored.updated_at,
      backend_reachable: health.ok,
      backend_health_error: health.error,
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to read tunnel config" },
      { status: 500 },
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { url?: string };
    const normalized = normalizeTunnelUrl(String(body.url || ""));
    if (!normalized) {
      return NextResponse.json({ error: "Tunnel URL is required." }, { status: 400 });
    }

    const health = await probeBackendHealth(normalized);
    if (!health.ok) {
      return NextResponse.json(
        {
          error:
            health.error ||
            "Could not reach that backend. Start cloudflared and paste the full trycloudflare URL.",
        },
        { status: 400 },
      );
    }

    const saved = await writeStoredBackendTunnel(normalized);
    return NextResponse.json({
      ok: true,
      backend_url: saved.backend_url,
      updated_at: saved.updated_at,
      backend_reachable: true,
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to save tunnel URL" },
      { status: 400 },
    );
  }
}
