import type { ViewerSegment } from "@/lib/types";

type SegmentLike = Pick<ViewerSegment, "render_mode" | "remotion" | "selection">;

export function isRemotionSegment(segment: SegmentLike): boolean {
  return segment.render_mode === "remotion" && Boolean(segment.remotion?.composition);
}

export function segmentCountsAsReady(segment: SegmentLike): boolean {
  return isRemotionSegment(segment) || Boolean(segment.selection);
}

export function segmentNeedsBrollFetch(segment: SegmentLike): boolean {
  return !isRemotionSegment(segment) && !segment.selection;
}
