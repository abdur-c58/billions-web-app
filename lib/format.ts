import type { SegmentTiming } from "./types";
import { formatTimestampClock } from "./timestamp";

export function formatTiming(timing: SegmentTiming) {
  if (timing.export_start_seconds != null && timing.export_end_seconds != null) {
    const start = formatTimestampClock(timing.export_start_seconds);
    const end = formatTimestampClock(timing.export_end_seconds);
    const duration =
      timing.duration_seconds != null ? ` (${timing.duration_seconds.toFixed(1)}s)` : "";
    return `${start} → ${end}${duration}`;
  }

  if (timing.start_seconds == null) return "No timestamp";
  const start = timing.start_timecode || `${timing.start_seconds}s`;
  const end = timing.end_timecode || `${timing.end_seconds}s`;
  const duration =
    timing.duration_seconds != null ? ` (${timing.duration_seconds.toFixed(1)}s)` : "";
  return `${start} → ${end}${duration}`;
}

export function formatDuration(totalSeconds: number | null | undefined) {
  if (totalSeconds == null || Number.isNaN(totalSeconds)) return "";
  const seconds = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

export function truncateExportMessage(message: string | null | undefined, maxLen = 200) {
  const text = (message || "").trim();
  if (!text) return "Unknown error";
  if (text.length <= maxLen) return text;
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const lower = lines[i].toLowerCase();
    if (
      lower.includes("error") ||
      lower.includes("failed") ||
      lower.includes("cannot") ||
      lower.includes("conversion failed")
    ) {
      return lines[i].slice(0, maxLen);
    }
  }
  return `${text.slice(0, maxLen - 3)}...`;
}
