"use client";

import { useEffect, useState } from "react";

type ConnectionDebug = {
  temporary_debug: boolean;
  vercel: boolean;
  vercel_url: string | null;
  env: {
    BROLL_BACKEND_URL: string | null;
    BROLL_BACKEND_PORT: string;
    effective_backend_url: string;
    NEXT_PUBLIC_BROLL_BACKEND_URL: string | null;
    NEXT_PUBLIC_BROLL_BACKEND_PORT: string;
    audio_upload_url: string | null;
  };
  backend_reachable: boolean | null;
  backend_health_status: number | null;
  backend_health_error: string | null;
};

export function ConnectionDebugBanner() {
  const [info, setInfo] = useState<ConnectionDebug | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/debug/connection", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Debug endpoint returned ${response.status}`);
        }
        return response.json() as Promise<ConnectionDebug>;
      })
      .then((payload) => {
        if (!cancelled) setInfo(payload);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load connection info");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const reachable =
    info?.backend_reachable === true
      ? "reachable"
      : info?.backend_reachable === false
        ? "unreachable"
        : "checking";

  return (
    <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-100 lg:px-6">
      <p className="font-semibold uppercase tracking-wide text-amber-200/90">
        Temp debug — backend connection
      </p>
      {error ? (
        <p className="mt-1 text-red-200">{error}</p>
      ) : !info ? (
        <p className="mt-1 text-amber-100/80">Loading deployment connection info…</p>
      ) : (
        <div className="mt-1 space-y-1 font-mono text-[0.72rem] leading-relaxed text-amber-50/90">
          <p>
            <span className="text-amber-200/70">Host:</span>{" "}
            {info.vercel ? info.vercel_url || "Vercel" : "local Next.js"}
          </p>
          <p>
            <span className="text-amber-200/70">BROLL_BACKEND_URL:</span>{" "}
            {info.env.BROLL_BACKEND_URL || "(not set — using localhost fallback)"}
          </p>
          <p>
            <span className="text-amber-200/70">BROLL_BACKEND_PORT:</span> {info.env.BROLL_BACKEND_PORT}
          </p>
          <p>
            <span className="text-amber-200/70">Effective proxy target:</span>{" "}
            {info.env.effective_backend_url}
          </p>
          <p>
            <span className="text-amber-200/70">NEXT_PUBLIC_BROLL_BACKEND_URL:</span>{" "}
            {info.env.NEXT_PUBLIC_BROLL_BACKEND_URL || "(not set)"}
          </p>
          <p>
            <span className="text-amber-200/70">NEXT_PUBLIC_BROLL_BACKEND_PORT:</span>{" "}
            {info.env.NEXT_PUBLIC_BROLL_BACKEND_PORT}
          </p>
          <p>
            <span className="text-amber-200/70">Backend health:</span> {reachable}
            {info.backend_health_status != null ? ` (HTTP ${info.backend_health_status})` : ""}
            {info.backend_health_error ? ` — ${info.backend_health_error}` : ""}
          </p>
        </div>
      )}
    </div>
  );
}
