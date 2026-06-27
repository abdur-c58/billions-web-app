"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { fetchExportStatus } from "@/lib/export";
import { formatDuration } from "@/lib/format";
import { SegmentationHardwarePanel } from "@/components/SegmentationHardwarePanel";
import type { ExportSnapshot } from "@/lib/types";

const IDLE_SNAPSHOT: ExportSnapshot = {
  status: "idle",
  progress_percent: 0,
  message: "Waiting for export to start…",
};

export function ExportProgressView({
  projectId,
  projectLabel,
}: {
  projectId: string;
  projectLabel?: string | null;
}) {
  const [snapshot, setSnapshot] = useState<ExportSnapshot>(IDLE_SNAPSHOT);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    document.body.classList.add("progress-page-black");

    if (document.fullscreenEnabled && !document.fullscreenElement) {
      void document.documentElement.requestFullscreen().catch(() => {});
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
        const next = await fetchExportStatus(projectId);
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
  }, [projectId]);

  const percent = Math.max(0, Math.min(100, Math.round(snapshot.progress_percent ?? 0)));
  const percentLabel = `${percent}%`;
  const isComplete = percent >= 100;
  const showHardware = snapshot.status === "running" || Boolean(snapshot.hardware);
  const isDownloading = snapshot.stage === "download";
  const downloadSeconds = snapshot.download_seconds ?? 0;
  const renderSeconds = snapshot.render_seconds ?? 0;
  const showTimings =
    snapshot.status === "running" || snapshot.status === "done" || downloadSeconds > 0 || renderSeconds > 0;
  const displayName =
    snapshot.project_name || projectLabel || projectId.slice(0, 8);

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
      <Link
        href="/"
        className="absolute left-4 top-4 z-10 inline-flex items-center gap-2 rounded-[10px] border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white md:left-6"
        aria-label="Back to viewer"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </Link>

      <div className="flex h-full flex-col items-center justify-center px-4 pb-28">
        <p className="mb-4 text-center text-sm text-white/50">{displayName}</p>

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
              x="50%"
              y="50%"
              textAnchor="middle"
              dominantBaseline="central"
              fill={isComplete ? "#146b32" : "#000000"}
              stroke={isComplete ? "#5ecf8a" : "#bdbdbd"}
              strokeWidth="0.9"
              paintOrder="stroke fill"
            >
              {percentLabel}
            </text>
            <text
              className="progress-percent-text progress-percent-glow-stroke"
              x="50%"
              y="50%"
              textAnchor="middle"
              dominantBaseline="central"
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
        {showTimings ? (
          <div className="mt-4 flex items-center gap-3 text-[0.85rem]">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 ${
                isDownloading
                  ? "border-white/20 bg-white/10 text-white/90"
                  : "border-white/10 bg-white/5 text-white/60"
              }`}
            >
              <span className="text-white/40">Downloads</span>
              <span className="font-semibold tabular-nums">{formatDuration(downloadSeconds)}</span>
            </span>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 ${
                !isDownloading && snapshot.status === "running"
                  ? "border-[#e8c06a]/40 bg-[#e8c06a]/10 text-[#e8c06a]"
                  : "border-white/10 bg-white/5 text-white/60"
              }`}
            >
              <span className="opacity-60">Render</span>
              <span className="font-semibold tabular-nums">{formatDuration(renderSeconds)}</span>
            </span>
          </div>
        ) : null}
        {error ? (
          <p className="mt-2 w-full px-4 text-center text-[0.9rem] text-[#ffc9c9]">{error}</p>
        ) : snapshot.message ? (
          <p className="mt-2 w-full max-w-2xl px-4 text-center text-[0.9rem] text-[var(--muted)]/90">
            {snapshot.message}
          </p>
        ) : null}
      </div>

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
