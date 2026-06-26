import type { SegmentSelection } from "@/lib/types";

export type QualityTier = "none" | "good" | "mid" | "review" | "unknown";

export const QUALITY_LABELS: Record<QualityTier, string> = {
  none: "Missing",
  good: "Good",
  mid: "Mid",
  review: "Review",
  unknown: "Unknown",
};

export function computeQualityTier(selection?: SegmentSelection | null): QualityTier {
  if (!selection?.url) return "none";
  if (selection.confidence_source === "manual") return "good";
  if (selection.needs_review) return "review";
  if (selection.confidence == null) return "unknown";
  if (selection.confidence >= 0.72) return "good";
  if (selection.confidence >= 0.55) return "mid";
  return "review";
}

export function qualityTierClass(tier: QualityTier): string {
  switch (tier) {
    case "good":
      return "glow-chip glow-chip-good";
    case "mid":
      return "glow-chip glow-chip-mid";
    case "review":
      return "glow-chip glow-chip-review";
    case "unknown":
      return "glow-chip text-[var(--muted)]";
    default:
      return "glow-chip text-[var(--muted)]";
  }
}

export function summarizeJudgments(
  segments: Array<{ selection?: SegmentSelection | null }>,
): Record<QualityTier, number> {
  const counts: Record<QualityTier, number> = {
    none: 0,
    good: 0,
    mid: 0,
    review: 0,
    unknown: 0,
  };
  for (const segment of segments) {
    const tier =
      segment.selection?.quality_tier ?? computeQualityTier(segment.selection);
    counts[tier] += 1;
  }
  return counts;
}

export const EMPTY_JUDGMENT_SUMMARY = summarizeJudgments([]);

export function judgmentDetail(selection?: SegmentSelection | null): string {
  if (!selection) return "";
  const tier = selection.quality_tier ?? computeQualityTier(selection);
  const label =
    tier === "unknown" || tier === "none"
      ? null
      : selection.quality_label || QUALITY_LABELS[tier];
  return [
    label,
    selection.confidence != null
      ? `${Math.round(selection.confidence * 100)}% confidence`
      : null,
    selection.confidence_source ? `via ${selection.confidence_source}` : null,
    selection.ai_reason,
    selection.ai_skipped ? `AI skipped: ${selection.ai_skipped}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}
