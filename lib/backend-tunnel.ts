import { GetObjectCommand, PutObjectCommand } from "@aws-sdk/client-s3";
import { getR2Client } from "@/lib/r2-client";

export const TUNNEL_CONFIG_KEY = ".config/broll_backend_tunnel.json";

export type BackendTunnelConfig = {
  backend_url: string;
  updated_at: string;
};

export function normalizeTunnelUrl(raw: string): string {
  let url = raw.trim();
  if (!url) return "";
  if (!/^https?:\/\//i.test(url)) {
    url = `https://${url}`;
  }
  return url.replace(/\/+$/, "");
}

export function isValidTunnelUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return false;
    if (parsed.protocol === "http:" && !["localhost", "127.0.0.1"].includes(parsed.hostname)) {
      return false;
    }
    return Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

export async function readStoredBackendTunnel(): Promise<BackendTunnelConfig | null> {
  try {
    const { client, bucket } = getR2Client();
    const response = await client.send(
      new GetObjectCommand({
        Bucket: bucket,
        Key: TUNNEL_CONFIG_KEY,
      }),
    );
    const raw = await response.Body?.transformToString();
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<BackendTunnelConfig>;
    const backendUrl = normalizeTunnelUrl(String(parsed.backend_url || ""));
    if (!backendUrl || !isValidTunnelUrl(backendUrl)) return null;
    return {
      backend_url: backendUrl,
      updated_at: String(parsed.updated_at || new Date().toISOString()),
    };
  } catch (error) {
    const status = (error as { name?: string })?.name;
    if (status === "NoSuchKey") return null;
    return null;
  }
}

export async function writeStoredBackendTunnel(backendUrl: string): Promise<BackendTunnelConfig> {
  const normalized = normalizeTunnelUrl(backendUrl);
  if (!isValidTunnelUrl(normalized)) {
    throw new Error("Enter a valid https:// tunnel URL (e.g. https://….trycloudflare.com).");
  }

  const payload: BackendTunnelConfig = {
    backend_url: normalized,
    updated_at: new Date().toISOString(),
  };

  const { client, bucket } = getR2Client();
  await client.send(
    new PutObjectCommand({
      Bucket: bucket,
      Key: TUNNEL_CONFIG_KEY,
      Body: JSON.stringify(payload, null, 2),
      ContentType: "application/json",
    }),
  );

  return payload;
}

export async function getEffectiveBackendUrl(): Promise<string | null> {
  const stored = await readStoredBackendTunnel();
  if (stored?.backend_url) return stored.backend_url;

  const fromEnv = process.env.BROLL_BACKEND_URL?.replace(/\/$/, "");
  if (fromEnv) return fromEnv;

  if (process.env.VERCEL) return null;

  const port = process.env.BROLL_BACKEND_PORT || "8766";
  return `http://127.0.0.1:${port}`;
}

export async function probeBackendHealth(backendUrl: string): Promise<{
  ok: boolean;
  status: number | null;
  error: string | null;
}> {
  try {
    const response = await fetch(`${backendUrl}/api/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
    return {
      ok: response.ok,
      status: response.status,
      error: response.ok ? null : `HTTP ${response.status}`,
    };
  } catch (error) {
    return {
      ok: false,
      status: null,
      error: error instanceof Error ? error.message : "Health check failed",
    };
  }
}
