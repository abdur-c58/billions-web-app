"use client";

import { AlertTriangle, Check, Loader2, Sparkles } from "lucide-react";
import { WhisperModelSelect } from "@/components/WhisperModelSelect";
import type { TimestampAlignment } from "@/lib/project";
import type { WhisperModel } from "@/lib/whisper";

type SegmentationAlignmentSummaryProps = {
  alignment: TimestampAlignment;
  compact?: boolean;
  className?: string;
  whisperModel?: WhisperModel;
  onWhisperModelChange?: (model: WhisperModel) => void;
  onResegment?: () => void;
  resegmenting?: boolean;
  resegmentDisabled?: boolean;
  jobMessage?: string | null;
  jobProgress?: number | null;
};

function alignmentPercent(aligned: number, total: number): number {
  if (!total) return 0;
  return Math.round((aligned / total) * 100);
}

function isWeakAlignment(alignment: TimestampAlignment): boolean {
  const total = alignment.total_segments || 0;
  if (!total) return false;
  const percent = alignmentPercent(alignment.aligned_segments, total);
  return percent < 85;
}

export function SegmentationAlignmentSummary({
  alignment,
  compact = false,
  className = "",
  whisperModel,
  onWhisperModelChange,
  onResegment,
  resegmenting = false,
  resegmentDisabled = false,
  jobMessage,
  jobProgress,
}: SegmentationAlignmentSummaryProps) {
  const total = alignment.total_segments || 0;
  const aligned = alignment.aligned_segments || 0;
  const timed = alignment.timed_segments || 0;
  const interpolated = alignment.interpolated_segments || 0;
  const estimated = alignment.estimated_segments || 0;
  const duration = alignment.total_duration_timecode || "";
  const filledWithoutMatch = interpolated + estimated;
  const matchPercent = alignmentPercent(aligned, total);
  const weak = isWeakAlignment(alignment);
  const usedModel = alignment.whisper_model?.trim() || null;

  if (compact) {
    const parts = [`Whisper ${aligned}/${total}`, `timestamps ${timed}/${total}`];
    if (duration) parts.push(duration);
    return (
      <p className={`text-xs text-[var(--muted)] ${className}`.trim()}>
        {parts.join(" · ")}
      </p>
    );
  }

  const Icon = weak ? AlertTriangle : Check;
  const borderClass = weak
    ? "border-[rgba(255,193,7,0.45)] bg-[rgba(255,193,7,0.08)]"
    : "border-[rgba(94,207,138,0.45)] bg-[rgba(94,207,138,0.08)]";
  const iconClass = weak ? "text-[#ffe8a3]" : "text-[#5ecf8a]";
  const titleClass = weak ? "text-[#ffe8a3]" : "text-[#5ecf8a]";

  return (
    <div className={`rounded-[10px] border px-4 py-3 ${borderClass} ${className}`.trim()}>
      <div className="flex items-start gap-2.5">
        <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconClass}`} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className={`text-sm font-semibold ${titleClass}`}>
                {weak ? "Segmentation finished with gaps" : "Segmentation complete"}
              </p>
              {usedModel ? (
                <p className="mt-0.5 text-xs text-[var(--muted)]">
                  Last run used <span className="font-medium text-[var(--foreground)]">{usedModel}</span>
                </p>
              ) : null}
            </div>
            <p className="text-sm font-semibold tabular-nums text-[var(--foreground)]">
              {matchPercent}% Whisper match
            </p>
          </div>

          <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/25">
            <div
              className={`h-full rounded-full transition-[width] duration-500 ${
                weak ? "bg-[#e8c06a]" : "bg-[#5ecf8a]"
              }`}
              style={{ width: `${matchPercent}%` }}
            />
          </div>

          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[var(--muted)]">Whisper-aligned</dt>
              <dd className="font-semibold tabular-nums text-[var(--foreground)]">
                {aligned} / {total} segments
              </dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Timestamps assigned</dt>
              <dd className="font-semibold tabular-nums text-[var(--foreground)]">
                {timed} / {total} segments
              </dd>
            </div>
            {duration ? (
              <div>
                <dt className="text-[var(--muted)]">Narration span</dt>
                <dd className="font-semibold tabular-nums text-[var(--foreground)]">{duration}</dd>
              </div>
            ) : null}
            {filledWithoutMatch > 0 ? (
              <div>
                <dt className="text-[var(--muted)]">Guessed timing</dt>
                <dd className="font-semibold tabular-nums text-[var(--foreground)]">
                  {filledWithoutMatch}
                  {interpolated > 0 && estimated > 0
                    ? ` (${interpolated} interpolated, ${estimated} estimated)`
                    : interpolated > 0
                      ? " interpolated"
                      : " estimated"}
                </dd>
              </div>
            ) : null}
          </dl>

          {weak ? (
            <div className="mt-3 space-y-2 text-xs leading-5 text-[var(--muted)]">
              <p>
                {filledWithoutMatch} segments were timed without a direct Whisper word match. B-roll
                still works, but cuts may be less precise on those lines.
              </p>
              <p>
                Try a larger model below (e.g. <strong className="text-[var(--foreground)]">large-v3</strong>
                ) and re-run. Each model keeps its own transcript cache on your GPU.
              </p>
            </div>
          ) : null}

          {whisperModel && onWhisperModelChange && onResegment ? (
            <div className="mt-4 flex flex-col gap-3 border-t border-[var(--border)] pt-4 sm:flex-row sm:items-end">
              <WhisperModelSelect
                value={whisperModel}
                onValueChange={onWhisperModelChange}
                disabled={resegmenting || resegmentDisabled}
              />
              <button
                type="button"
                className="glow-btn-primary inline-flex h-10 items-center justify-center gap-2 rounded-[10px] px-4 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
                disabled={resegmenting || resegmentDisabled}
                onClick={onResegment}
              >
                {resegmenting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Re-segmenting…
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Re-run Auto-segment
                  </>
                )}
              </button>
            </div>
          ) : null}

          {resegmenting && (jobMessage || jobProgress != null) ? (
            <div className="mt-3 text-xs text-[var(--muted)]">
              <div className="flex items-center justify-between gap-3">
                <span>{jobMessage || "Running Whisper…"}</span>
                {jobProgress != null ? (
                  <span className="tabular-nums">{jobProgress}%</span>
                ) : null}
              </div>
              {jobProgress != null ? (
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-black/25">
                  <div
                    className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-300"
                    style={{ width: `${Math.max(0, Math.min(100, jobProgress))}%` }}
                  />
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
