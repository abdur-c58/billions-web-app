import type { ViewerSegment } from "./types";

export type ExportTimelineEntry = {
  segment: ViewerSegment;
  exportStart: number;
  exportEnd: number;
};

export function parseTimestamp(input: string): number | null {
  const raw = input.trim();
  if (!raw) return null;

  const withoutSuffix = raw.endsWith("s") ? raw.slice(0, -1).trim() : raw;
  if (/^\d+(\.\d+)?$/.test(withoutSuffix)) {
    const value = Number(withoutSuffix);
    return Number.isFinite(value) && value >= 0 ? value : null;
  }

  if (!raw.includes(":")) return null;

  const parts = raw.split(":").map((part) => part.trim());
  if (parts.length < 2 || parts.length > 3) return null;
  if (parts.some((part) => !/^\d+(\.\d+)?$/.test(part))) return null;

  const numbers = parts.map(Number);
  if (parts.length === 2) {
    const [minutes, seconds] = numbers;
    return minutes * 60 + seconds;
  }

  const [hours, minutes, seconds] = numbers;
  return hours * 3600 + minutes * 60 + seconds;
}

export function formatTimestampClock(totalSeconds: number) {
  const safe = Math.max(0, totalSeconds);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  const wholeSeconds = Math.floor(seconds);
  const fraction = Math.round((seconds - wholeSeconds) * 1000);

  if (hours > 0) {
    const base = `${hours}:${String(minutes).padStart(2, "0")}:${String(wholeSeconds).padStart(2, "0")}`;
    return fraction > 0 ? `${base}.${String(fraction).padStart(3, "0").replace(/0+$/, "")}` : base;
  }

  const base = `${minutes}:${String(wholeSeconds).padStart(2, "0")}`;
  return fraction > 0 ? `${base}.${String(fraction).padStart(3, "0").replace(/0+$/, "")}` : base;
}

export function buildExportTimeline(segments: ViewerSegment[]): ExportTimelineEntry[] {
  const sorted = [...segments].sort((a, b) => a.segment_id - b.segment_id);
  const timeline: ExportTimelineEntry[] = [];
  let cursor = 0;

  for (const segment of sorted) {
    const timing = segment.timing;
    const duration = timing.duration_seconds;
    if (duration == null || duration <= 0) continue;

    const exportStart =
      timing.export_start_seconds != null ? timing.export_start_seconds : cursor;
    const exportEnd =
      timing.export_end_seconds != null ? timing.export_end_seconds : exportStart + duration;

    timeline.push({
      segment,
      exportStart,
      exportEnd,
    });
    cursor = exportEnd;
  }

  return timeline;
}

export function getExportDuration(
  segments: ViewerSegment[],
  videoDurationS?: number | null,
): number {
  const timeline = buildExportTimeline(segments);
  const exportTotal = timeline.at(-1)?.exportEnd ?? 0;
  if (videoDurationS == null || videoDurationS <= 0) return exportTotal;
  return Math.min(exportTotal, videoDurationS);
}

export function findSegmentAtExportTime(
  segments: ViewerSegment[],
  seconds: number,
  videoDurationS?: number | null,
): ExportTimelineEntry | null {
  if (!Number.isFinite(seconds) || seconds < 0) return null;

  const maxTime = getExportDuration(segments, videoDurationS);
  const clamped = Math.min(seconds, maxTime);
  const timeline = buildExportTimeline(segments);
  if (!timeline.length) return null;

  const exact = timeline.find(
    (entry) => clamped >= entry.exportStart && clamped < entry.exportEnd,
  );
  if (exact) return exact;

  const started = timeline.filter((entry) => entry.exportStart <= clamped);
  if (started.length) {
    return started.reduce((best, entry) =>
      entry.exportStart > best.exportStart ? entry : best,
    );
  }

  return timeline[0];
}

/** Narration/audio alignment time — not the same as exported MP4 timeline. */
export function findSegmentAtNarrationTime(
  segments: ViewerSegment[],
  seconds: number,
): ViewerSegment | null {
  if (!Number.isFinite(seconds) || seconds < 0) return null;

  const timed = segments.filter((segment) => segment.timing.start_seconds != null);
  if (!timed.length) return null;

  const exact = timed.find((segment) => {
    const start = segment.timing.start_seconds!;
    const end = segment.timing.end_seconds ?? start;
    return seconds >= start && seconds < end;
  });
  if (exact) return exact;

  const started = timed.filter((segment) => segment.timing.start_seconds! <= seconds);
  if (started.length) {
    return started.reduce((best, segment) =>
      segment.timing.start_seconds! > best.timing.start_seconds! ? segment : best,
    );
  }

  return timed.reduce((best, segment) =>
    segment.timing.start_seconds! < best.timing.start_seconds! ? segment : best,
  );
}
