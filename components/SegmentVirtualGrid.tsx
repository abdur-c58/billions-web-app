"use client";

import { useWindowVirtualizer } from "@tanstack/react-virtual";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FetchProvider } from "@/hooks/useBrollViewer";
import type { ScriptFormat, ViewerSegment } from "@/lib/types";
import { SegmentCard } from "@/components/SegmentCard";

const CARD_MIN_WIDTH = 300;
const GRID_GAP_PX = 14;
const ROW_HEIGHT_ESTIMATE = 920;

function columnCountForWidth(width: number): number {
  return Math.max(1, Math.floor((width + GRID_GAP_PX) / (CARD_MIN_WIDTH + GRID_GAP_PX)));
}

type SegmentVirtualGridProps = {
  segments: ViewerSegment[];
  scriptFormat: ScriptFormat;
  customQueries: Record<number, string>;
  loadingIds: Set<number>;
  focusedSegmentId: number | null;
  onCustomQueryChange: (segmentId: number, value: string) => void;
  onFetch: (segmentId: number, refetch: boolean, provider?: FetchProvider) => void;
  onSelectAlternative: (
    segmentId: number,
    searchQuery: string,
    videoIndex: number,
  ) => void;
  onChooseFromStorage: (segmentId: number) => void;
  onFlagClip: (segmentId: number) => void;
  remotionPreviewUrls: Record<number, string>;
  remotionBusyIds: Set<number>;
  onSaveRemotionProps: (segmentId: number, props: Record<string, unknown>) => Promise<void>;
  onPreviewRemotion: (segmentId: number, props: Record<string, unknown>) => Promise<void>;
  onSuggestRemotionPrompt: (
    segmentId: number,
    prompt: string,
    currentProps: Record<string, unknown>,
  ) => Promise<{ props: Record<string, unknown>; summary: string }>;
};

export function SegmentVirtualGrid({
  segments,
  scriptFormat,
  customQueries,
  loadingIds,
  focusedSegmentId,
  onCustomQueryChange,
  onFetch,
  onSelectAlternative,
  onChooseFromStorage,
  onFlagClip,
  remotionPreviewUrls,
  remotionBusyIds,
  onSaveRemotionProps,
  onPreviewRemotion,
  onSuggestRemotionPrompt,
}: SegmentVirtualGridProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [columnCount, setColumnCount] = useState(1);
  const [scrollMargin, setScrollMargin] = useState(0);

  const updateLayout = useCallback(() => {
    const node = listRef.current;
    if (!node) return;
    setColumnCount(columnCountForWidth(node.clientWidth));
    setScrollMargin(node.offsetTop);
  }, []);

  useEffect(() => {
    updateLayout();
    const node = listRef.current;
    if (!node) return;

    const observer = new ResizeObserver(updateLayout);
    observer.observe(node);
    window.addEventListener("resize", updateLayout);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateLayout);
    };
  }, [updateLayout]);

  const rows = useMemo(() => {
    const grouped: ViewerSegment[][] = [];
    for (let index = 0; index < segments.length; index += columnCount) {
      grouped.push(segments.slice(index, index + columnCount));
    }
    return grouped;
  }, [segments, columnCount]);

  const virtualizer = useWindowVirtualizer({
    count: rows.length,
    estimateSize: () => ROW_HEIGHT_ESTIMATE,
    overscan: 2,
    scrollMargin,
  });

  useEffect(() => {
    if (focusedSegmentId == null) return;
    const segmentIndex = segments.findIndex(
      (segment) => segment.segment_id === focusedSegmentId,
    );
    if (segmentIndex < 0) return;

    const rowIndex = Math.floor(segmentIndex / columnCount);
    const timer = window.setTimeout(() => {
      virtualizer.scrollToIndex(rowIndex, { align: "center", behavior: "smooth" });
    }, 80);
    return () => window.clearTimeout(timer);
    // scrollToIndex is stable enough; avoid re-running on every virtualizer render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedSegmentId, segments, columnCount]);

  const gridTemplateColumns = `repeat(${columnCount}, minmax(0, 1fr))`;

  return (
    <div ref={listRef} className="w-full px-4 py-4 pb-10 lg:px-6">
      <div
        className="relative w-full"
        style={{ height: `${virtualizer.getTotalSize()}px` }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const rowSegments = rows[virtualRow.index];
          if (!rowSegments) return null;

          return (
            <div
              key={virtualRow.key}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              className="absolute left-0 top-0 grid w-full items-start gap-3.5"
              style={{
                gridTemplateColumns,
                transform: `translateY(${virtualRow.start - scrollMargin}px)`,
              }}
            >
              {rowSegments.map((segment) => (
                <SegmentCard
                  key={segment.segment_id}
                  segment={segment}
                  scriptFormat={scriptFormat}
                  customQuery={
                    customQueries[segment.segment_id] ??
                    segment.selection?.custom_query ??
                    ""
                  }
                  isLoading={loadingIds.has(segment.segment_id)}
                  isFocused={focusedSegmentId === segment.segment_id}
                  onCustomQueryChange={(value) =>
                    onCustomQueryChange(segment.segment_id, value)
                  }
                  onFetch={(refetch, provider = "mix") =>
                    onFetch(segment.segment_id, refetch, provider)
                  }
                  onSelectAlternative={(videoIndex) =>
                    onSelectAlternative(
                      segment.segment_id,
                      segment.search_query,
                      videoIndex,
                    )
                  }
                  onChooseFromStorage={() => onChooseFromStorage(segment.segment_id)}
                  onFlagClip={() => onFlagClip(segment.segment_id)}
                  remotionPreviewUrl={remotionPreviewUrls[segment.segment_id] ?? null}
                  remotionBusy={remotionBusyIds.has(segment.segment_id)}
                  onSaveRemotionProps={(props) =>
                    onSaveRemotionProps(segment.segment_id, props)
                  }
                  onPreviewRemotion={(props) =>
                    onPreviewRemotion(segment.segment_id, props)
                  }
                  onSuggestRemotionPrompt={(prompt, currentProps) =>
                    onSuggestRemotionPrompt(segment.segment_id, prompt, currentProps)
                  }
                />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
