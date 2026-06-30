"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Link2, Loader2, X } from "lucide-react";
import { invalidateBackendUrlCache } from "@/lib/api";
import { invalidateAudioUploadUrlCache } from "@/lib/project";
import { cn } from "@/lib/utils";

type TunnelConfig = {
  backend_url: string | null;
  tunnel_source: string | null;
  tunnel_updated_at: string | null;
  backend_reachable: boolean | null;
  backend_health_error: string | null;
};

function shouldUseDirectBackend(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host.endsWith(".vercel.app") || (!host.includes("localhost") && !host.includes("127.0.0.1"));
}

export function BackendTunnelConnect() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [config, setConfig] = useState<TunnelConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const payload = await fetch("/api/config", { cache: "no-store" }).then(
        (response) => response.json() as Promise<TunnelConfig>,
      );
      setConfig(payload);
      if (payload.backend_url && shouldUseDirectBackend()) {
        setInput(payload.backend_url);
      }
    } catch {
      setConfig(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    setNotice(null);
    try {
      const response = await fetch("/api/config/tunnel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: input }),
      });
      const payload = (await response.json()) as { error?: string; backend_url?: string };
      if (!response.ok) {
        throw new Error(payload.error || "Failed to connect");
      }
      invalidateBackendUrlCache();
      invalidateAudioUploadUrlCache();
      await refresh();
      setNotice("Backend connected — saved for all devices.");
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect");
    } finally {
      setConnecting(false);
    }
  };

  const connected = Boolean(config?.backend_url);
  const reachable = config?.backend_reachable === true;
  const statusColor = !connected
    ? "bg-[var(--muted)]"
    : reachable
      ? "bg-emerald-400"
      : "bg-amber-400";

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setError(null);
          setOpen(true);
        }}
        className={cn(
          "inline-flex items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-sm font-medium transition-colors",
          connected && reachable
            ? "bg-emerald-500/10 text-emerald-300"
            : "text-[var(--muted)] hover:bg-[var(--surface-raised)] hover:text-[var(--foreground)]",
        )}
        title={
          connected
            ? config?.backend_url || "Backend configured"
            : "Connect Cloudflare tunnel"
        }
      >
        <span className={cn("size-2 rounded-full", statusColor)} />
        <Link2 className="h-4 w-4" />
        <span className="hidden sm:inline">Backend</span>
      </button>

      {notice ? (
        <p className="fixed right-4 top-16 z-40 rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
          {notice}
        </p>
      ) : null}

      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[90] grid place-items-center bg-black/65 p-4 backdrop-blur-[2px]"
            onClick={() => setOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.98, y: 6 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: 4 }}
              className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#11131a] p-5 shadow-2xl"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold text-white">Connect backend tunnel</h3>
                  <p className="mt-1 text-sm text-white/60">
                    Paste your trycloudflare URL once — it is saved in R2 and shared across
                    devices.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="rounded-md p-1 text-white/50 hover:bg-white/10 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {loading ? (
                <p className="mt-4 inline-flex items-center gap-2 text-sm text-white/60">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading current backend…
                </p>
              ) : (
                <div className="mt-4 space-y-3">
                  {connected ? (
                    <div className="rounded-xl border border-white/10 bg-black/25 p-3 text-sm">
                      <p className="font-medium text-white/85">Current backend</p>
                      <p className="mt-1 break-all font-mono text-xs text-white/70">
                        {config?.backend_url}
                      </p>
                      <p className="mt-2 text-xs text-white/45">
                        Source: {config?.tunnel_source || "unknown"}
                        {config?.tunnel_updated_at
                          ? ` · updated ${new Date(config.tunnel_updated_at).toLocaleString()}`
                          : ""}
                      </p>
                      <p
                        className={cn(
                          "mt-1 text-xs",
                          reachable ? "text-emerald-300" : "text-amber-300",
                        )}
                      >
                        {reachable
                          ? "Reachable"
                          : config?.backend_health_error || "Not reachable — paste a new URL"}
                      </p>
                    </div>
                  ) : null}

                  <label className="block text-xs font-medium uppercase tracking-wide text-white/45">
                    Cloudflare tunnel URL
                  </label>
                  <input
                    type="url"
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    placeholder="https://something-random.trycloudflare.com"
                    className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none ring-0 placeholder:text-white/30 focus:border-white/25"
                  />
                  <p className="text-xs text-white/40">
                    Run{" "}
                    <code className="text-white/60">
                      cloudflared tunnel --url http://127.0.0.1:8766
                    </code>{" "}
                    locally, then paste the https link shown in the terminal.
                  </p>
                </div>
              )}

              {error ? (
                <p className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                  {error}
                </p>
              ) : null}

              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="glow-btn-secondary rounded-[10px] px-3 py-2 text-sm font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={connecting || !input.trim()}
                  onClick={() => void handleConnect()}
                  className="glow-btn-primary inline-flex items-center gap-2 rounded-[10px] px-3 py-2 text-sm font-semibold disabled:opacity-55"
                >
                  {connecting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4" />
                  )}
                  Connect
                </button>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}
