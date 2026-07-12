import type { ViewerSegment } from "@/lib/types";

type SegmentLike = Pick<ViewerSegment, "render_mode" | "remotion" | "selection">;

export type RemotionLayout = "split-right" | "full" | "overlay";

export function isRemotionSegment(segment: SegmentLike): boolean {
  return segment.render_mode === "remotion" && Boolean(segment.remotion?.composition);
}

export function remotionLayout(segment: SegmentLike): RemotionLayout {
  const layout = segment.remotion?.layout;
  if (layout === "split-right" || layout === "full" || layout === "overlay") {
    return layout;
  }
  if (segment.remotion?.composition === "TitleCard") {
    return "full";
  }
  if (segment.remotion?.composition === "FactCard") {
    return "split-right";
  }
  return "full";
}

export function isSplitScreenRemotion(segment: SegmentLike): boolean {
  return isRemotionSegment(segment) && remotionLayout(segment) === "split-right";
}

export function isOverlayRemotion(segment: SegmentLike): boolean {
  return isRemotionSegment(segment) && remotionLayout(segment) === "overlay";
}

export function remotionNeedsBroll(segment: SegmentLike): boolean {
  return isSplitScreenRemotion(segment) || isOverlayRemotion(segment);
}

export function segmentCountsAsReady(segment: SegmentLike): boolean {
  if (remotionNeedsBroll(segment)) {
    return Boolean(segment.selection) && Boolean(segment.remotion?.composition);
  }
  if (isRemotionSegment(segment)) {
    return true;
  }
  return Boolean(segment.selection);
}

export function segmentNeedsBrollFetch(segment: SegmentLike): boolean {
  if (remotionNeedsBroll(segment)) {
    return !segment.selection;
  }
  return !isRemotionSegment(segment) && !segment.selection;
}
