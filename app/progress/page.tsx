"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { SegmentationHardwarePanel } from "@/components/SegmentationHardwarePanel";
import type { ExportSnapshot } from "@/lib/types";

const IDLE_SNAPSHOT: ExportSnapshot = {
  status: "idle",
  progress_percent: 0,
  message: "Waiting for export to start…",
};

export default function ProgressPage() {
  const [snapshot, setSnapshot] = useState<ExportSnapshot>(IDLE_SNAPSHOT);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    document.body.classList.add("progress-page-black");

    if (document.fullscreenEnabled && !document.fullscreenElement) {
      void document.documentElement.requestFullscreen().catch(() => {
        // Browser may block if not triggered by a direct user gesture — silently ignore.
      });
    }

    return () => {
      document.body.classList.remove("progress-page-black");
      if (document.fullscreenElement) {
        void document.exitFullscreen().catch(() => {});
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const next = await apiFetch<ExportSnapshot>("/api/export/status");
        if (!cancelled) {
          setSnapshot(next);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to read export status");
        }
      } finally {
        if (!cancelled) {
          timerRef.current = window.setTimeout(poll, 1000);
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, []);

  const percent = Math.max(0, Math.min(100, Math.round(snapshot.progress_percent ?? 0)));
  const percentLabel = `${percent}%`;
  const isComplete = percent >= 100;
  const showHardware = snapshot.status === "running" || Boolean(snapshot.hardware);
  const etaText = useMemo(() => {
    if (snapshot.status === "running") {
      return snapshot.eta_seconds != null
        ? `ETA ${formatDuration(snapshot.eta_seconds)}`
        : "ETA calculating…";
    }
    if (snapshot.status === "done") return "Done";
    if (snapshot.status === "error") return "Export failed";
    if (snapshot.status === "interrupted") return "Export interrupted";
    return "Waiting for export…";
  }, [snapshot]);

  return (
    <main className="fixed inset-0 z-50 overflow-hidden bg-black text-[var(--foreground)]">
      {/* Back button — fixed top-left */}
      <Link
        href="/"
        className="absolute left-4 top-4 z-10 inline-flex items-center gap-2 rounded-[10px] border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white md:left-6"
        aria-label="Back to viewer"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </Link>

      {/* Centred progress content */}
      <div className="flex h-full flex-col items-center justify-center px-4 pb-28">
        <div
          className={`progress-percent-wrap${isComplete ? " progress-percent-wrap--complete" : ""}`}
          aria-label={`${percent} percent`}
        >
          <svg
            className="progress-percent-svg"
            viewBox="0 0 520 160"
            role="img"
            aria-hidden="true"
          >
            <defs>
              <linearGradient
                id="progressPercentStrokeGlow"
                gradientUnits="userSpaceOnUse"
                x1="-180"
                y1="0"
                x2="180"
                y2="0"
              >
                <stop offset="0%" stopColor={isComplete ? "#3d9e62" : "#8f8f8f"} />
                <stop offset="38%" stopColor={isComplete ? "#3d9e62" : "#8f8f8f"} />
                <stop offset="50%" stopColor={isComplete ? "#b8ffd4" : "#f5f5f5"} />
                <stop offset="62%" stopColor={isComplete ? "#3d9e62" : "#8f8f8f"} />
                <stop offset="100%" stopColor={isComplete ? "#3d9e62" : "#8f8f8f"} />
                <animate attributeName="x1" from="-180" to="700" dur="0.95s" repeatCount="indefinite" />
                <animate attributeName="x2" from="180" to="1060" dur="0.95s" repeatCount="indefinite" />
              </linearGradient>
            </defs>
            <text
              className="progress-percent-text"
              x="50%" y="50%"
              textAnchor="middle" dominantBaseline="central"
              fill={isComplete ? "#146b32" : "#000000"}
              stroke={isComplete ? "#5ecf8a" : "#bdbdbd"}
              strokeWidth="0.9" paintOrder="stroke fill"
            >
              {percentLabel}
            </text>
            <text
              className="progress-percent-text progress-percent-glow-stroke"
              x="50%" y="50%"
              textAnchor="middle" dominantBaseline="central"
              fill="none"
              stroke="url(#progressPercentStrokeGlow)"
              strokeWidth="0.9"
            >
              {percentLabel}
            </text>
          </svg>
        </div>

        <div className="progress-bar-shell progress-bar-gold mt-8 w-full">
          <div className="export-progress-track !h-[9px] rounded-full bg-[rgba(255,255,255,0.07)]">
            <div className="export-progress-fill-group" style={{ width: `${percent}%` }}>
              <div className="export-progress-fill-ambient !h-[18px]" />
              <div className="export-progress-fill !h-[5px]" />
            </div>
            <div className="export-progress-glow-layer" style={{ width: `${percent}%` }}>
              <span className="export-progress-glow-beam !h-[7px]" aria-hidden="true" />
            </div>
          </div>
        </div>

        <p className="mt-8 w-full px-4 text-center text-[clamp(0.95rem,1.8vw,1.4rem)] text-[var(--muted)]">
          {etaText}
        </p>
        {error ? (
          <p className="mt-2 w-full px-4 text-center text-[0.9rem] text-[#ffc9c9]">{error}</p>
        ) : snapshot.message ? (
          <p className="mt-2 w-full max-w-2xl px-4 text-center text-[0.9rem] text-[var(--muted)]/90">
            {snapshot.message}
          </p>
        ) : null}
      </div>

      {/* Hardware panel — fixed bottom */}
      {showHardware ? (
        <div className="absolute bottom-5 left-4 right-4 mx-auto w-full max-w-lg pb-2">
          <SegmentationHardwarePanel
            compact
            heading="Export hardware"
            hardware={snapshot.hardware}
            idleProbe={snapshot.status === "running" && !snapshot.hardware}
          />
        </div>
      ) : null}
    </main>
  );
}
