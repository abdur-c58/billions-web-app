"use client";

import { Check, AlertTriangle } from "lucide-react";
import type { TimestampAlignment } from "@/lib/project";

type SegmentationAlignmentSummaryProps = {
  alignment: TimestampAlignment;
  compact?: boolean;
  className?: string;
};

function isPartialAlignment(alignment: TimestampAlignment): boolean {
  const total = alignment.total_segments || 0;
  if (!total) return false;
  return alignment.aligned_segments < total || alignment.timed_segments < total;
}

export function SegmentationAlignmentSummary({
  alignment,
  compact = false,
  className = "",
}: SegmentationAlignmentSummaryProps) {
  const total = alignment.total_segments || 0;
  const aligned = alignment.aligned_segments || 0;
  const timed = alignment.timed_segments || 0;
  const interpolated = alignment.interpolated_segments || 0;
  const estimated = alignment.estimated_segments || 0;
  const duration = alignment.total_duration_timecode || "";
  const partial = isPartialAlignment(alignment);

  if (compact) {
    const parts = [`Whisper ${aligned}/${total}`, `timestamps ${timed}/${total}`];
    if (duration) parts.push(duration);
    return (
      <p className={`text-xs text-[var(--muted)] ${className}`.trim()}>
        {parts.join(" · ")}
      </p>
    );
  }

  const Icon = partial ? AlertTriangle : Check;
  const borderClass = partial
    ? "border-[rgba(255,193,7,0.45)] bg-[rgba(255,193,7,0.08)]"
    : "border-[rgba(94,207,138,0.45)] bg-[rgba(94,207,138,0.08)]";
  const iconClass = partial ? "text-[#ffe8a3]" : "text-[#5ecf8a]";
  const titleClass = partial ? "text-[#ffe8a3]" : "text-[#5ecf8a]";

  return (
    <div
      className={`rounded-[10px] border px-4 py-3 ${borderClass} ${className}`.trim()}
    >
      <div className="flex items-start gap-2.5">
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconClass}`} />
        <div className="min-w-0 flex-1">
          <p className={`text-sm font-semibold ${titleClass}`}>
            {partial ? "Segmentation complete with gaps" : "Segmentation complete"}
          </p>
          <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[var(--muted)]">Whisper-aligned segments</dt>
              <dd className="font-semibold tabular-nums text-[var(--foreground)]">
                {aligned} / {total}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Timestamps assigned</dt>
              <dd className="font-semibold tabular-nums text-[var(--foreground)]">
                {timed} / {total}
              </dd>
            </div>
            {duration ? (
              <div>
                <dt className="text-[var(--muted)]">Narration span</dt>
                <dd className="font-semibold tabular-nums text-[var(--foreground)]">{duration}</dd>
              </div>
            ) : null}
            {interpolated > 0 || estimated > 0 ? (
              <div>
                <dt className="text-[var(--muted)]">Filled without Whisper match</dt>
                <dd className="font-semibold tabular-nums text-[var(--foreground)]">
                  {interpolated + estimated}
                  {interpolated > 0 && estimated > 0
                    ? ` (${interpolated} interpolated, ${estimated} estimated)`
                    : interpolated > 0
                      ? " interpolated"
                      : " estimated"}
                </dd>
              </div>
            ) : null}
          </dl>
          {partial ? (
            <p className="mt-2 text-xs text-[var(--muted)]">
              Some segments could not be matched to the audio. Re-upload a full narration file or
              re-run Auto-segment if the counts look wrong.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
