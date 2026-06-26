"use client";

import { useEffect, useState } from "react";
import { Cpu, Gpu } from "lucide-react";
import { fetchWhisperHardware, type SegmentationHardware } from "@/lib/project";

function formatGb(mb: number | null | undefined) {
  if (mb == null) return "—";
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb} MB`;
}

function UsageBar({
  label,
  percent,
  detail,
  compact,
}: {
  label: string;
  percent: number | null | undefined;
  detail?: string;
  compact?: boolean;
}) {
  const value = percent == null ? 0 : Math.min(100, Math.max(0, percent));
  return (
    <div>
      <div
        className={`mb-1 flex items-center justify-between gap-2 text-[var(--muted)] ${
          compact ? "text-[9px]" : "text-[11px]"
        }`}
      >
        <span>{label}</span>
        <span className="tabular-nums text-[var(--foreground)]">
          {percent != null ? `${percent}%` : "—"}
          {detail ? ` · ${detail}` : ""}
        </span>
      </div>
      <div
        className={`overflow-hidden rounded-full bg-[var(--surface-raised)] ${
          compact ? "h-1" : "h-1.5"
        }`}
      >
        <div
          className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-500"
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

type SegmentationHardwarePanelProps = {
  hardware?: SegmentationHardware | null;
  idleProbe?: boolean;
  compact?: boolean;
  heading?: string;
};

export function SegmentationHardwarePanel({
  hardware,
  idleProbe = false,
  compact = false,
  heading,
}: SegmentationHardwarePanelProps) {
  const [idle, setIdle] = useState<SegmentationHardware | null>(null);

  useEffect(() => {
    if (!idleProbe || hardware) return;
    void fetchWhisperHardware()
      .then(setIdle)
      .catch(() => setIdle(null));
  }, [hardware, idleProbe]);

  const stats = hardware ?? idle;
  if (!stats) return null;

  const usingGpu = stats.device === "cuda";
  const Icon = usingGpu ? Gpu : Cpu;
  const deviceLabel = usingGpu
    ? `GPU · ${stats.gpu_name || "CUDA"}`
    : stats.gpu_name
      ? `CPU (GPU: ${stats.gpu_name})`
      : "CPU";

  const vramUsed = stats.gpu_memory_used_mb ?? stats.torch_memory_used_mb;
  const vramTotal = stats.gpu_memory_total_mb;
  const vramPercent =
    vramUsed != null && vramTotal != null && vramTotal > 0
      ? Math.round((vramUsed / vramTotal) * 100)
      : null;

  const ramPercent =
    stats.ram_used_mb != null && stats.ram_total_mb != null && stats.ram_total_mb > 0
      ? Math.round((stats.ram_used_mb / stats.ram_total_mb) * 100)
      : null;

  const panelTitle = heading ?? `Whisper on ${deviceLabel}`;

  if (compact) {
    return (
      <div className="rounded-lg border border-white/10 bg-black/50 px-2.5 py-2 backdrop-blur-sm">
        <div className="flex items-center gap-1.5 text-[10px] font-medium text-white/75">
          <Icon className="h-3 w-3 text-[var(--accent)]" />
          <span className="truncate">{panelTitle}</span>
          {usingGpu ? (
            <span className="ml-auto shrink-0 rounded-full bg-[rgba(76,175,80,0.12)] px-1.5 py-px text-[8px] font-semibold uppercase tracking-wide text-[#9be7a8]">
              CUDA
            </span>
          ) : null}
        </div>
        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5">
          {usingGpu ? (
            <>
              <UsageBar compact label="GPU" percent={stats.gpu_util_percent} />
              <UsageBar
                compact
                label="VRAM"
                percent={vramPercent}
                detail={
                  vramUsed != null && vramTotal != null
                    ? `${formatGb(vramUsed)}/${formatGb(vramTotal)}`
                    : undefined
                }
              />
            </>
          ) : null}
          <UsageBar compact label="CPU" percent={stats.cpu_percent} />
          <UsageBar
            compact
            label="RAM"
            percent={ramPercent}
            detail={
              stats.ram_used_mb != null && stats.ram_total_mb != null
                ? `${formatGb(stats.ram_used_mb)}/${formatGb(stats.ram_total_mb)}`
                : undefined
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)] p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--foreground)]">
        <Icon className="h-4 w-4 text-[var(--accent)]" />
        <span>{panelTitle}</span>
        {usingGpu ? (
          <span className="rounded-full bg-[rgba(76,175,80,0.15)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#9be7a8]">
            CUDA
          </span>
        ) : (
          <span className="rounded-full bg-[rgba(255,193,7,0.15)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#ffd666]">
            CPU
          </span>
        )}
      </div>

      {stats.hint ? <p className="mt-2 text-xs text-[#ffc9c9]">{stats.hint}</p> : null}

      <div className="mt-3 space-y-2.5">
        {usingGpu ? (
          <>
            <UsageBar label="GPU utilization" percent={stats.gpu_util_percent} />
            <UsageBar
              label="VRAM"
              percent={vramPercent}
              detail={
                vramUsed != null && vramTotal != null
                  ? `${formatGb(vramUsed)} / ${formatGb(vramTotal)}`
                  : undefined
              }
            />
          </>
        ) : null}
        <UsageBar label="CPU" percent={stats.cpu_percent} />
        <UsageBar
          label="RAM"
          percent={ramPercent}
          detail={
            stats.ram_used_mb != null && stats.ram_total_mb != null
              ? `${formatGb(stats.ram_used_mb)} / ${formatGb(stats.ram_total_mb)}`
              : undefined
          }
        />
      </div>

      {stats.torch_version ? (
        <p className="mt-2 text-[10px] text-[var(--muted)]">
          PyTorch {stats.torch_version}
          {stats.cuda_version ? ` · CUDA ${stats.cuda_version}` : ""}
        </p>
      ) : null}
    </div>
  );
}
