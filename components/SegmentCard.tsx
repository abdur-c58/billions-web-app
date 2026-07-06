"use client";

import { memo, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Flag, HardDrive, Play, Sparkles } from "lucide-react";
import type { PexelsVideo, ScriptFormat, ViewerSegment } from "@/lib/types";
import { formatTiming } from "@/lib/format";
import type { FetchProvider } from "@/hooks/useBrollViewer";
import { RemotionSegmentEditor } from "@/components/RemotionSegmentEditor";
import {
  computeQualityTier,
  judgmentDetail,
  qualityTierClass,
  QUALITY_LABELS,
} from "@/lib/judgment";

type SegmentCardProps = {
  segment: ViewerSegment;
  scriptFormat: ScriptFormat;
  customQuery: string;
  isLoading: boolean;
  isFocused?: boolean;
  onCustomQueryChange: (value: string) => void;
  onFetch: (refetch: boolean, provider?: FetchProvider) => void;
  onSelectAlternative: (videoIndex: number) => void;
  onChooseFromStorage: () => void;
  onFlagClip: () => void;
  remotionPreviewUrl?: string | null;
  remotionBusy?: boolean;
  onSaveRemotionProps?: (props: Record<string, unknown>) => Promise<void>;
  onPreviewRemotion?: (props: Record<string, unknown>) => Promise<void>;
  onSuggestRemotionPrompt?: (
    prompt: string,
    currentProps: Record<string, unknown>,
  ) => Promise<{ props: Record<string, unknown>; summary: string }>;
};

function SegmentCardInner({
  segment,
  scriptFormat,
  customQuery,
  isLoading,
  isFocused = false,
  onCustomQueryChange,
  onFetch,
  onSelectAlternative,
  onChooseFromStorage,
  onFlagClip,
  remotionPreviewUrl = null,
  remotionBusy = false,
  onSaveRemotionProps,
  onPreviewRemotion,
  onSuggestRemotionPrompt,
}: SegmentCardProps) {
  const cardRef = useRef<HTMLElement | null>(null);
  const [inView, setInView] = useState(false);
  const [videoActive, setVideoActive] = useState(false);
  const [altExpanded, setAltExpanded] = useState(false);
  const selection = segment.selection;
  const hasSelection = Boolean(selection);
  const alternatives = segment._alternatives || [];
  const searchedWithCustom =
    selection?.query_used && selection.query_used !== segment.search_query;
  const qualityTier = selection?.quality_tier ?? computeQualityTier(selection);
  const qualityLabel = selection?.quality_label || QUALITY_LABELS[qualityTier];
  const detail = judgmentDetail(selection);
  const folderStatus = segment.folder_status;
  const isRemotion = segment.render_mode === "remotion" && Boolean(segment.remotion?.composition);
  const isFolderFormat = scriptFormat === "folder";
  const isStock = segment.category.trim().toLowerCase() === "stock";
  const showNoFolderWarning =
    isFolderFormat && !isStock && folderStatus?.expects_folder && !folderStatus.has_folder;
  const showShortageWarning =
    isFolderFormat && !isStock && folderStatus?.has_folder && folderStatus.shortage;
  const showFolderTypeBadge = isFolderFormat && !isStock;

  const cardGlowClass = isFocused
    ? "glow-card glow-card-focused"
    : isRemotion
      ? "glow-card glow-card-good"
    : segment.selection_flagged
      ? "glow-card glow-card-flagged"
      : qualityTier === "good"
        ? "glow-card glow-card-good"
        : qualityTier === "mid"
          ? "glow-card glow-card-mid"
          : qualityTier === "review"
            ? "glow-card glow-card-review"
            : hasSelection
              ? "glow-card"
              : "glow-card glow-card-warn";

  useEffect(() => {
    if (inView) return;
    const node = cardRef.current;
    if (!node) return;
    if (typeof window === "undefined" || !("IntersectionObserver" in window)) {
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { root: null, rootMargin: "200px 0px", threshold: 0 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [inView]);

  // Reset video/alt state when selection changes
  useEffect(() => {
    setVideoActive(false);
    setAltExpanded(false);
  }, [selection?.video_id]);

  return (
    <article
      id={`segment-card-${segment.segment_id}`}
      ref={cardRef}
      className={`flex min-w-0 flex-col overflow-hidden rounded-[14px] ${cardGlowClass}`}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 px-3 pt-2.5">
        <div className="text-[0.75rem] font-bold uppercase tracking-[0.08em] text-[var(--accent)] glow-accent-text">
          Segment {segment.segment_id}
        </div>
        <span className="glow-badge inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full bg-[rgba(229,229,229,0.12)] px-2 py-0.5 text-[0.68rem] text-[var(--foreground)]">
          {segment.beat}. {segment.label || "Untitled beat"}
        </span>
        <span className="glow-badge inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full bg-[rgba(229,229,229,0.12)] px-2 py-0.5 text-[0.68rem] text-[var(--foreground)]">
          {isRemotion
            ? `Remotion · ${segment.remotion?.composition}`
            : segment.search_query || "No search term"}
        </span>
        {showFolderTypeBadge ? (
          <span className="glow-badge inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full bg-[rgba(163,163,163,0.12)] px-2 py-0.5 text-[0.68rem] text-[var(--muted)]">
            Type: {segment.category}
          </span>
        ) : null}
        {searchedWithCustom ? (
          <span
            className="glow-badge inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full bg-[rgba(163,163,163,0.12)] px-2 py-0.5 text-[0.68rem] text-[var(--muted)]"
            title={selection?.query_used}
          >
            Custom: {selection?.query_used}
          </span>
        ) : null}
        <span
          className="glow-badge inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full bg-[rgba(163,163,163,0.12)] px-2 py-0.5 text-[0.68rem] text-[var(--muted)]"
          title={formatTiming(segment.timing)}
        >
          {formatTiming(segment.timing)}
        </span>
        {isRemotion ? (
          <span className="glow-badge inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full bg-[rgba(167,139,250,0.16)] px-2 py-0.5 text-[0.68rem] font-semibold text-violet-200">
            <Sparkles className="h-3 w-3 shrink-0" />
            Auto motion
          </span>
        ) : hasSelection ? (
          <span
            className={`inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full px-2 py-0.5 text-[0.68rem] font-semibold ${qualityTierClass(qualityTier)}`}
            title={detail}
          >
            {qualityLabel}
            {selection?.confidence != null
              ? ` · ${Math.round(selection.confidence * 100)}%`
              : ""}
          </span>
        ) : (
          <span
            className={`inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full px-2 py-0.5 text-[0.68rem] font-semibold ${qualityTierClass("none")}`}
          >
            Missing
          </span>
        )}
        {selection?.provider === "storage" ? (
          <span className="glow-badge inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap rounded-full bg-[rgba(163,163,163,0.12)] px-2 py-0.5 text-[0.68rem] text-[var(--muted)]">
            Storage
            {selection.loop ? " · loop" : ""}
          </span>
        ) : null}
        {segment.selection_flagged ? (
          <span
            className="glow-chip glow-chip-flagged inline-flex max-w-full items-center gap-1 overflow-hidden text-ellipsis whitespace-nowrap px-2 py-0.5 text-[0.68rem] font-semibold"
            title="This clip is flagged and will never be used in future fetches"
          >
            <Flag className="h-3 w-3 shrink-0" />
            Flagged
          </span>
        ) : null}
      </div>

      {showNoFolderWarning ? (
        <div className="mx-3 rounded-lg border border-amber-500/35 bg-amber-500/10 px-3 py-2 text-[0.72rem] leading-snug text-amber-100">
          No <code className="text-[var(--foreground)]">B-Roll/{segment.category}/</code> folder
          found. Manual fetch will use the API with &quot;{segment.search_query}&quot;.
        </div>
      ) : null}

      {showShortageWarning ? (
        <div className="mx-3 rounded-lg border border-amber-500/25 bg-amber-500/8 px-3 py-2 text-[0.72rem] leading-snug text-amber-100/90">
          Only {folderStatus?.clip_count} clip
          {folderStatus?.clip_count === 1 ? "" : "s"} in{" "}
          <code className="text-[var(--foreground)]">B-Roll/{segment.category}/</code> — use Folder
          Fetch to choose how extras are handled.
        </div>
      ) : null}

      <div className="flex flex-1 flex-col gap-2.5 px-3 py-2.5 pb-3">
        <div className="grid gap-2">
          <div className="glow-video-frame relative aspect-video overflow-hidden rounded-[10px] bg-black">
            {isRemotion ? (
              remotionPreviewUrl ? (
                <video
                  src={remotionPreviewUrl}
                  controls
                  autoPlay
                  muted
                  playsInline
                  preload="metadata"
                  className="block h-full w-full object-contain"
                />
              ) : (
                <div className="flex h-full flex-col justify-between bg-[linear-gradient(145deg,#071018,#132337)] p-4 text-left text-white">
                  <div>
                    <p className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-violet-200">
                      {segment.remotion?.composition}
                    </p>
                    <p className="mt-2 text-sm font-semibold leading-snug">
                      {String(segment.remotion?.props?.title || segment.label || "Motion segment")}
                    </p>
                    {segment.remotion?.props?.body ? (
                      <p className="mt-2 line-clamp-4 text-[0.72rem] leading-relaxed text-white/75">
                        {String(segment.remotion.props.body)}
                      </p>
                    ) : segment.remotion?.props?.subtitle ? (
                      <p className="mt-2 line-clamp-3 text-[0.72rem] leading-relaxed text-white/75">
                        {String(segment.remotion.props.subtitle)}
                      </p>
                    ) : null}
                  </div>
                  <p className="text-[0.68rem] text-white/55">
                    Customize below, then Preview
                  </p>
                </div>
              )
            ) : hasSelection && videoActive ? (
              <video
                src={selection?.url}
                poster={selection?.thumbnail || undefined}
                controls
                autoPlay
                muted
                playsInline
                loop
                preload="metadata"
                className="block h-full w-full object-cover"
              />
            ) : hasSelection ? (
              <button
                type="button"
                className="group relative h-full w-full cursor-pointer border-0 bg-transparent p-0"
                onClick={() => setVideoActive(true)}
                title="Click to play"
              >
                {inView && selection?.thumbnail ? (
                  <img
                    src={selection.thumbnail}
                    alt={`Segment ${segment.segment_id} preview`}
                    loading="lazy"
                    decoding="async"
                    className="block h-full w-full object-cover opacity-80 transition-opacity group-hover:opacity-60"
                  />
                ) : (
                  <div className="h-full w-full bg-black" />
                )}
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm transition-transform group-hover:scale-110">
                    <Play className="h-4 w-4 fill-white" />
                  </span>
                </div>
              </button>
            ) : (
              <div className="grid h-full place-items-center p-3 text-center text-[0.78rem] text-[var(--muted)]">
                No b-roll yet — click Fetch
              </div>
            )}
            {isLoading || remotionBusy ? (
              <div className="absolute inset-0 grid place-items-center bg-black/55 text-sm text-white">
                {remotionBusy ? "Rendering preview…" : "Fetching…"}
              </div>
            ) : null}
          </div>

          {detail && !isRemotion ? (
            <p className="text-[0.72rem] leading-snug text-[var(--muted)]" title={detail}>
              {detail}
            </p>
          ) : null}

          {isRemotion ? (
            onSaveRemotionProps && onPreviewRemotion && onSuggestRemotionPrompt ? (
              <RemotionSegmentEditor
                segment={segment}
                isBusy={isLoading || remotionBusy}
                previewUrl={remotionPreviewUrl}
                onSave={onSaveRemotionProps}
                onPreview={onPreviewRemotion}
                onSuggestPrompt={onSuggestRemotionPrompt}
              />
            ) : (
              <p className="text-[0.72rem] leading-snug text-violet-200/80">
                This segment uses a Remotion composition instead of stock b-roll.
              </p>
            )
          ) : (
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              disabled={isLoading}
              onClick={() => onFetch(false)}
              className="glow-btn-primary rounded-lg px-2.5 py-1.5 text-[0.78rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
            >
              {hasSelection ? "Reload" : "Fetch"}
            </button>
            <button
              type="button"
              disabled={isLoading}
              onClick={() => onFetch(true, "mix")}
              className="glow-btn-secondary rounded-lg px-2.5 py-1.5 text-[0.78rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
            >
              Refetch
            </button>
            <button
              type="button"
              disabled={isLoading}
              onClick={() => onFetch(true, "pexels")}
              className="glow-btn-secondary rounded-lg px-2.5 py-1.5 text-[0.74rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
            >
              Refetch Pexels
            </button>
            <button
              type="button"
              disabled={isLoading}
              onClick={() => onFetch(true, "pixabay")}
              className="glow-btn-secondary rounded-lg px-2.5 py-1.5 text-[0.74rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
            >
              Refetch Pixabay
            </button>
            <button
              type="button"
              disabled={isLoading}
              onClick={() => onFetch(true, "random")}
              className="glow-btn-secondary rounded-lg px-2.5 py-1.5 text-[0.74rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
            >
              Refetch Random
            </button>
            <button
              type="button"
              disabled={isLoading}
              onClick={onChooseFromStorage}
              className="glow-btn-secondary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.74rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
              title="Pick a video from cloud storage"
            >
              <HardDrive className="h-3.5 w-3.5" />
              From storage
            </button>
            {hasSelection && !segment.selection_flagged ? (
              <button
                type="button"
                disabled={isLoading}
                onClick={onFlagClip}
                className="glow-btn-flag inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.74rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
                title="Never use this clip again in future fetches"
              >
                <Flag className="h-3.5 w-3.5" />
                Flag clip
              </button>
            ) : null}
            <div className="flex w-full min-w-0 items-center gap-2">
              <input
                type="text"
                value={customQuery}
                onChange={(event) => onCustomQueryChange(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    onFetch(true);
                  }
                }}
                placeholder="Custom search…"
                title={`Leave empty for default: ${segment.search_query || ""}`}
                className="glow-control min-w-0 flex-1 rounded-lg px-2.5 py-1.5 text-[0.78rem] text-[var(--foreground)] placeholder:text-[var(--muted)]"
              />
            </div>
            {selection?.pexels_url ? (
              <a
                href={selection.pexels_url}
                target="_blank"
                rel="noreferrer"
                className="w-full text-[0.72rem] text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                Pexels{selection.photographer ? ` · ${selection.photographer}` : ""}
              </a>
            ) : selection?.pixabay_url ? (
              <a
                href={selection.pixabay_url}
                target="_blank"
                rel="noreferrer"
                className="w-full text-[0.72rem] text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                Pixabay{selection.photographer ? ` · ${selection.photographer}` : ""}
              </a>
            ) : selection?.provider === "storage" ? (
              <span className="w-full text-[0.72rem] text-[var(--muted)]">
                Storage · {selection.name || selection.storage_key?.split("/").pop()}
                {selection.duration != null ? ` · ${selection.duration.toFixed(1)}s` : ""}
                {selection.loop ? " · loops on export" : ""}
              </span>
            ) : null}
          </div>
          )}

          {!isRemotion && alternatives.length > 0 ? (
            <div>
              <button
                type="button"
                className="flex items-center gap-1.5 text-[0.72rem] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
                onClick={() => setAltExpanded((prev) => !prev)}
              >
                {altExpanded ? (
                  <ChevronUp className="h-3.5 w-3.5" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5" />
                )}
                {altExpanded ? "Hide" : "Show"} alternatives ({alternatives.length})
              </button>
              {altExpanded ? (
                <div className="mt-1.5 grid grid-cols-[repeat(auto-fill,minmax(56px,1fr))] gap-1.5">
                  {alternatives.map((video: PexelsVideo, index) => (
                    <button
                      key={`${segment.segment_id}-alt-${video.video_id}-${index}`}
                      type="button"
                      title={`Use clip ${index + 1}`}
                      onClick={() => onSelectAlternative(index)}
                      className={`aspect-video overflow-hidden rounded-md border-2 bg-black p-0 transition-shadow ${
                        video.video_id === selection?.video_id
                          ? "border-[var(--accent)] shadow-[0_0_16px_rgba(255,255,255,0.2)]"
                          : "border-transparent hover:border-[rgba(255,255,255,0.15)]"
                      }`}
                    >
                      <img
                        src={video.thumbnail || undefined}
                        alt={`Alternative ${index + 1}`}
                        loading="lazy"
                        decoding="async"
                        className="block h-full w-full object-cover"
                      />
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <div>
          <h3 className="mb-1 text-[0.72rem] uppercase tracking-[0.06em] text-[var(--muted)]">
            Narration
          </h3>
          <p
            className="mb-1.5 line-clamp-3 text-[0.82rem] leading-[1.45] text-[#d4d4d4]"
            title={segment.content}
          >
            {segment.content}
          </p>
          <div
            className="line-clamp-2 text-[0.74rem] text-[var(--muted)]"
            title={segment.description || ""}
          >
            <strong>Visual:</strong> {segment.description || "—"}
          </div>
        </div>
      </div>
    </article>
  );
}

export const SegmentCard = memo(SegmentCardInner);
