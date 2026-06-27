"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AudioLines, Clapperboard, Cpu } from "lucide-react";
import { fetchActivity, type ActivityJob, type ActivitySnapshot } from "@/lib/activity";

const POLL_INTERVAL_MS = 2500;

const JOB_STYLES: Record<
  ActivityJob["type"],
  { icon: typeof AudioLines; fill: string; accent: string }
> = {
  whisper: {
    icon: AudioLines,
    fill: "rgba(94, 207, 138, 0.18)",
    accent: "#5ecf8a",
  },
  export: {
    icon: Clapperboard,
    fill: "rgba(232, 192, 106, 0.18)",
    accent: "#e8c06a",
  },
};

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function JobPill({ job }: { job: ActivityJob }) {
  const style = JOB_STYLES[job.type];
  const Icon = style.icon;
  const percent = clampPercent(job.progress_percent);
  const project = job.project_name || job.project_id?.slice(0, 8) || "Project";

  const pill = (
    <div
      className="relative flex min-w-[150px] items-center gap-2 overflow-hidden rounded-full border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5"
      title={`${job.label} · ${project} — ${job.message}`}
    >
      <span
        className="pointer-events-none absolute inset-y-0 left-0 transition-[width] duration-700 ease-out"
        style={{ width: `${percent}%`, backgroundColor: style.fill }}
        aria-hidden="true"
      />
      <Icon
        className="relative h-3.5 w-3.5 shrink-0 animate-pulse"
        style={{ color: style.accent }}
      />
      <span className="relative flex min-w-0 flex-col leading-tight">
        <span className="truncate text-[11px] font-medium text-[var(--foreground)]">
          {job.label}
        </span>
        <span className="truncate text-[10px] text-[var(--muted)]">{project}</span>
      </span>
      <span
        className="relative ml-auto text-[11px] font-semibold tabular-nums"
        style={{ color: style.accent }}
      >
        {percent}%
      </span>
    </div>
  );

  if (job.type === "export" && job.project_id) {
    return (
      <Link href={`/progress/${job.project_id}`} className="shrink-0 transition-opacity hover:opacity-90">
        {pill}
      </Link>
    );
  }

  return pill;
}

function GpuPill({ utilization }: { utilization: number | null }) {
  const hasValue = utilization != null;
  const percent = hasValue ? clampPercent(utilization) : 0;
  // Warm the colour up as the GPU works harder.
  const accent = !hasValue
    ? "var(--muted)"
    : percent >= 80
      ? "#e8c06a"
      : percent >= 40
        ? "#7fd0a3"
        : "#6f8fb0";

  return (
    <div
      className="relative flex items-center gap-1.5 overflow-hidden rounded-full border border-[var(--border)] bg-[var(--surface-raised)] px-2.5 py-1.5"
      title="GPU utilization"
    >
      <span
        className="pointer-events-none absolute inset-y-0 left-0 transition-[width] duration-700 ease-out"
        style={{ width: `${percent}%`, backgroundColor: "rgba(127, 208, 163, 0.14)" }}
        aria-hidden="true"
      />
      <Cpu className="relative h-3.5 w-3.5 shrink-0" style={{ color: accent }} />
      <span className="relative text-[11px] font-medium text-[var(--muted)]">GPU</span>
      <span
        className="relative text-[11px] font-semibold tabular-nums"
        style={{ color: accent }}
      >
        {hasValue ? `${percent}%` : "—"}
      </span>
    </div>
  );
}

export function GlobalActivityIndicator() {
  const [snapshot, setSnapshot] = useState<ActivitySnapshot | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const next = await fetchActivity();
        if (!cancelled) setSnapshot(next);
      } catch {
        if (!cancelled) setSnapshot(null);
      } finally {
        if (!cancelled) {
          timerRef.current = window.setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, []);

  if (!snapshot || !snapshot.busy || snapshot.jobs.length === 0) {
    return null;
  }

  return (
    <div className="ml-auto flex items-center gap-2">
      {snapshot.jobs.map((job) => (
        <JobPill key={`${job.type}-${job.project_id ?? "current"}`} job={job} />
      ))}
      <GpuPill utilization={snapshot.gpu?.utilization_percent ?? null} />
    </div>
  );
}
