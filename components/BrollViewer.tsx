"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Flag, Clapperboard, Clock, Download, FolderOpen, Loader2, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ExportAudioModal } from "@/components/ExportAudioModal";
import { FlagClipModal } from "@/components/FlagClipModal";
import { StorageClipSelectModal } from "@/components/StorageClipSelectModal";
import { FolderFetchModal } from "@/components/FolderFetchModal";
import { SegmentVirtualGrid } from "@/components/SegmentVirtualGrid";
import { useBrollViewer, type FetchProvider } from "@/hooks/useBrollViewer";
import { EMPTY_JUDGMENT_SUMMARY } from "@/lib/judgment";
import type { FolderFetchPlan, FolderShortageStrategy } from "@/lib/types";

export function BrollViewer({ onBackToProjects }: { onBackToProjects?: () => void }) {
  const viewer = useBrollViewer();
  const router = useRouter();
  const [exportConfirmOpen, setExportConfirmOpen] = useState(false);
  const [storagePickerSegmentId, setStoragePickerSegmentId] = useState<number | null>(null);
  const [storagePickerBusy, setStoragePickerBusy] = useState(false);
  const [folderFetchOpen, setFolderFetchOpen] = useState(false);
  const [folderFetchBusy, setFolderFetchBusy] = useState(false);
  const [folderFetchPlan, setFolderFetchPlan] = useState<FolderFetchPlan | null>(null);
  const [folderFetchError, setFolderFetchError] = useState<string | null>(null);
  const folderFormatEnabled = viewer.scriptFormat === "folder";
  const summary = viewer.judgmentSummary ?? EMPTY_JUDGMENT_SUMMARY;
  const exportActive = ["running", "done", "error", "interrupted"].includes(
    viewer.exportSnapshot.status,
  );

  const fetchingIds = [...viewer.loadingIds].sort((a, b) => a - b);
  const showFetchActivity = fetchingIds.length > 0 || viewer.batchProgress !== null;
  const fetchProgressPercent = viewer.batchProgress
    ? Math.min(
        100,
        Math.max(
          0,
          Math.round((viewer.batchProgress.done / Math.max(1, viewer.batchProgress.total)) * 100),
        ),
      )
    : 0;

  const handleCustomQueryChange = useCallback(
    (segmentId: number, value: string) => {
      viewer.setCustomQueries((current) => ({
        ...current,
        [segmentId]: value,
      }));
    },
    [viewer.setCustomQueries],
  );

  const handleFetch = useCallback(
    (segmentId: number, refetch: boolean, provider: FetchProvider = "mix") => {
      void viewer.fetchSegmentWithRetry(segmentId, refetch, false, provider);
    },
    [viewer.fetchSegmentWithRetry],
  );

  const handleSelectAlternative = useCallback(
    (segmentId: number, searchQuery: string, videoIndex: number) => {
      void viewer.selectAlternative(segmentId, searchQuery, videoIndex);
    },
    [viewer.selectAlternative],
  );

  const handleFlagClip = useCallback(
    (segmentId: number) => {
      void viewer.flagClip(segmentId);
    },
    [viewer.flagClip],
  );

  const storagePickerSegment = useMemo(() => {
    if (storagePickerSegmentId == null) return null;
    return viewer.segments.find((segment) => segment.segment_id === storagePickerSegmentId) ?? null;
  }, [storagePickerSegmentId, viewer.segments]);

  const handleChooseFromStorage = useCallback((segmentId: number) => {
    setStoragePickerSegmentId(segmentId);
  }, []);

  const openFolderFetch = useCallback(async () => {
    setFolderFetchOpen(true);
    setFolderFetchPlan(null);
    setFolderFetchError(null);
    try {
      const plan = await viewer.loadFolderFetchPreview();
      setFolderFetchPlan(plan);
    } catch (error) {
      setFolderFetchError(
        error instanceof Error ? error.message : "Failed to load folder fetch preview",
      );
    }
  }, [viewer]);

  const reloadFolderFetch = useCallback(
    async (strategy?: FolderShortageStrategy) => {
      setFolderFetchError(null);
      try {
        const plan = await viewer.loadFolderFetchPreview(strategy);
        setFolderFetchPlan(plan);
      } catch (error) {
        setFolderFetchError(
          error instanceof Error ? error.message : "Failed to load folder fetch preview",
        );
      }
    },
    [viewer],
  );

  const handleConfirmFolderFetch = useCallback(
    async (strategy?: FolderShortageStrategy) => {
      setFolderFetchBusy(true);
      try {
        await viewer.applyFolderFetch(strategy);
        setFolderFetchOpen(false);
        setFolderFetchPlan(null);
      } catch {
        // Error toast handled in hook.
      } finally {
        setFolderFetchBusy(false);
      }
    },
    [viewer],
  );

  const handleConfirmStorageClip = useCallback(
    async (payload: {
      storageKey: string;
      name: string;
      duration: number | null;
      loop: boolean;
    }) => {
      if (storagePickerSegmentId == null) return;
      const segment = viewer.segments.find((item) => item.segment_id === storagePickerSegmentId);
      if (!segment) return;

      setStoragePickerBusy(true);
      try {
        await viewer.selectStorageClip(storagePickerSegmentId, segment.search_query, payload);
        setStoragePickerSegmentId(null);
      } catch {
        // Error toast handled in hook.
      } finally {
        setStoragePickerBusy(false);
      }
    },
    [storagePickerSegmentId, viewer],
  );

  return (
    <div className="glow-page w-full text-[var(--foreground)]">
      <header className="glow-header w-full border-b border-[var(--border)] px-4 py-4 lg:px-6">
        <div className="flex items-start gap-3">
          <Clapperboard className="glow-icon mt-0.5 h-5 w-5 text-[var(--muted)]" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg font-semibold tracking-tight lg:text-xl">B-Roll Viewer</h1>
              {onBackToProjects ? (
                <button
                  type="button"
                  onClick={onBackToProjects}
                  className="rounded-[8px] border border-[var(--border)] px-2 py-0.5 text-xs font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
                >
                  All projects
                </button>
              ) : null}
            </div>
            <p className="mt-0.5 text-sm text-[var(--muted)]">{viewer.title}</p>
            <p className="mt-0.5 text-xs text-[var(--muted)]">
              {viewer.projectFolder}
            </p>
            {!viewer.backendReady ? (
              <p className="mt-1 text-[0.82rem] text-[#ffc9c9]">
                API offline — run <code className="text-[var(--foreground)]">npm run dev:all</code>{" "}
                from the project root to start the Python backend on port 8766.
              </p>
            ) : null}
          </div>
        </div>

        <div className="mt-3.5 flex flex-wrap items-center gap-3">
          <label className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
            <input
              type="search"
              value={viewer.searchQuery}
              onChange={(event) => viewer.setSearchQuery(event.target.value)}
              placeholder="Filter segments, beats, or search terms…"
              className="glow-control w-full rounded-[10px] py-2.5 pl-9 pr-3 text-[var(--foreground)] placeholder:text-[var(--muted)]"
            />
          </label>

          <form
            className="flex min-w-[240px] items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              viewer.seekToTimestamp();
            }}
          >
            <label className="relative min-w-[180px] flex-1">
              <Clock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
              <input
                type="text"
                value={viewer.timestampSeekInput}
                onChange={(event) => viewer.setTimestampSeekInput(event.target.value)}
                placeholder="Seek in exported video (1:23)"
                className="glow-control w-full rounded-[10px] py-2.5 pl-9 pr-3 text-[var(--foreground)] placeholder:text-[var(--muted)]"
              />
            </label>
            <button
              type="submit"
              className="glow-btn-secondary shrink-0 rounded-[10px] px-3 py-2.5 text-sm font-semibold"
            >
              Go
            </button>
          </form>

          <select
            value={viewer.beatFilter}
            onChange={(event) => viewer.setBeatFilter(event.target.value)}
            className="glow-control min-w-[220px] rounded-[10px] px-3 py-2.5 text-[var(--foreground)]"
          >
            <option value="">All beats</option>
            {viewer.beats.map((beat) => {
              const label =
                viewer.segments.find((segment) => segment.beat === beat)?.label ||
                `Beat ${beat}`;
              return (
                <option key={beat} value={beat}>
                  {beat}. {label}
                </option>
              );
            })}
          </select>

          <select
            value={viewer.statusFilter}
            onChange={(event) =>
              viewer.setStatusFilter(event.target.value as "" | "missing" | "selected")
            }
            className="glow-control min-w-[220px] rounded-[10px] px-3 py-2.5 text-[var(--foreground)]"
          >
            <option value="">All segments</option>
            <option value="missing">Missing selection</option>
            <option value="selected">Has selection</option>
          </select>

          <select
            value={viewer.qualityFilter}
            onChange={(event) =>
              viewer.setQualityFilter(
                event.target.value as "" | "good" | "mid" | "review" | "none" | "unknown",
              )
            }
            className="glow-control min-w-[220px] rounded-[10px] px-3 py-2.5 text-[var(--foreground)]"
          >
            <option value="">All quality</option>
            <option value="good">Good picks</option>
            <option value="mid">Mid confidence</option>
            <option value="review">Needs review</option>
            <option value="none">Missing b-roll</option>
            <option value="unknown">Unknown quality</option>
          </select>

          <button
            type="button"
            disabled={
              !folderFormatEnabled ||
              viewer.batchRunning ||
              viewer.exportRunning ||
              !viewer.backendReady
            }
            onClick={() => void openFolderFetch()}
            className="glow-btn-secondary inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
            title={
              folderFormatEnabled
                ? "Assign clips from B-Roll storage folders by segment type"
                : "Folder Fetch requires a folder-format script.json (string type per segment)"
            }
          >
            <FolderOpen className="h-4 w-4" />
            Folder Fetch
          </button>

          <button
            type="button"
            disabled={viewer.batchRunning || viewer.exportRunning || !viewer.backendReady}
            onClick={() => void viewer.fetchMissing()}
            className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
          >
            Fetch missing only
          </button>

          <button
            type="button"
            disabled={viewer.batchRunning || viewer.exportRunning || !viewer.backendReady}
            onClick={() => void viewer.refetchAll()}
            className="glow-btn-primary inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
          >
            <RefreshCw className={`h-4 w-4 ${viewer.batchRunning ? "animate-spin" : ""}`} />
            Refetch all
          </button>
          <button
            type="button"
            disabled={viewer.batchRunning || viewer.exportRunning || !viewer.backendReady}
            onClick={() => void viewer.refetchUnscored()}
            className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
          >
            Rescan unscored
          </button>
          <button
            type="button"
            disabled={viewer.batchRunning || viewer.exportRunning || !viewer.backendReady}
            onClick={() => void viewer.refetchReview("mix")}
            className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
          >
            Refetch review (mix)
          </button>
          <button
            type="button"
            disabled={viewer.batchRunning || viewer.exportRunning || !viewer.backendReady}
            onClick={() => void viewer.refetchReview("pexels")}
            className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
          >
            Review Pexels
          </button>
          <button
            type="button"
            disabled={viewer.batchRunning || viewer.exportRunning || !viewer.backendReady}
            onClick={() => void viewer.refetchReview("pixabay")}
            className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
          >
            Review Pixabay
          </button>

          <div className="ml-auto flex flex-wrap items-center gap-2 text-sm text-[var(--muted)]">
            <span className="glow-chip glow-chip-good px-2 py-0.5">Good {summary.good}</span>
            <span className="glow-chip glow-chip-mid px-2 py-0.5">Mid {summary.mid}</span>
            <span className="glow-chip glow-chip-review px-2 py-0.5">
              Review {summary.review}
            </span>
            <span>
              {viewer.selectedCount}/{viewer.segments.length} selected ·{" "}
              {viewer.visibleSegments.length} shown
            </span>
            {viewer.aiJudge.enabled ? (
              <span className="glow-chip px-2 py-0.5" title="OpenAI judge calls remaining today">
                AI {viewer.aiJudge.remaining ?? 0}/{viewer.aiJudge.max_calls ?? 0}
              </span>
            ) : null}
          </div>
        </div>

        {showFetchActivity ? (
          <div
            className="glow-fetch-activity mt-2.5"
            role="status"
            aria-live="polite"
            aria-label="B-roll fetch activity"
          >
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.84rem]">
              <span className="inline-flex items-center gap-2 font-semibold text-[var(--foreground)]">
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--accent)]" />
                {viewer.batchProgress?.status === "waiting" ? (
                  <>
                    {viewer.batchProgress.label}: retrying pass {viewer.batchProgress.pass} in{" "}
                    {viewer.batchProgress.waitSeconds ?? 0}s
                    <span className="font-normal text-[var(--muted)]">
                      · {viewer.batchProgress.total} remaining
                    </span>
                  </>
                ) : viewer.batchProgress ? (
                  <>
                    {viewer.batchProgress.label} · pass {viewer.batchProgress.pass} ·{" "}
                    {viewer.batchProgress.done}/{viewer.batchProgress.total}
                    <span className="font-normal text-[var(--muted)]">
                      · {viewer.fetchConcurrency} parallel
                    </span>
                  </>
                ) : (
                  "Fetching b-roll"
                )}
              </span>
            </div>
            {viewer.batchProgress ? (
              <div className="fetch-progress-wrapper">
                <div className="export-progress-track">
                  <div
                    className="export-progress-fill-group"
                    style={{ width: `${fetchProgressPercent}%` }}
                  >
                    <div className="export-progress-fill-ambient" />
                    <div className="export-progress-fill" />
                  </div>
                  <div
                    className="export-progress-glow-layer"
                    style={{ width: `${fetchProgressPercent}%` }}
                  >
                    <span className="export-progress-glow-beam" aria-hidden="true" />
                  </div>
                </div>
                <div className="fetch-progress-label">{fetchProgressPercent}%</div>
              </div>
            ) : null}
            {fetchingIds.length > 0 ? (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-[0.72rem] uppercase tracking-[0.06em] text-[var(--muted)]">
                  Active
                </span>
                {fetchingIds.map((segmentId) => (
                  <span
                    key={segmentId}
                    className="glow-chip glow-chip-active px-2 py-0.5 text-[0.72rem] font-semibold tabular-nums"
                  >
                    #{segmentId}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="mt-2.5 flex flex-wrap items-center gap-2.5 overflow-visible border-t border-[rgba(255,255,255,0.06)] pt-2.5">
          {viewer.exportRunning ? (
            <Link
              href="/progress"
              className="glow-btn-primary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold"
            >
              Exporting… View progress
            </Link>
          ) : (
            <button
              type="button"
              disabled={viewer.batchRunning || !viewer.backendReady}
              onClick={() => setExportConfirmOpen(true)}
              className="glow-btn-primary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
            >
              Export final video
            </button>
          )}

          {viewer.exportRunning ? (
            <button
              type="button"
              onClick={() => void viewer.cancelExport()}
              className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold"
            >
              Cancel export
            </button>
          ) : null}

          <Link
            href="/duplicates"
            className="glow-btn-secondary inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold"
          >
            Duplicate clips
          </Link>

          <Link
            href="/flagged"
            className="glow-btn-secondary inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold"
          >
            Flagged clips
          </Link>

          <a
            href="/api/export/download"
            className={`glow-btn-secondary inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold ${
              viewer.exportSnapshot.status === "done" ? "" : "pointer-events-none opacity-55"
            }`}
            download
          >
            <Download className="h-4 w-4" />
            Download MP4
          </a>

          <div className="min-w-[200px] flex-1 overflow-visible text-[0.86rem] text-[var(--muted)]">
            <span>{viewer.exportProgressText}</span>
            {exportActive ? (
              <>
                <div className="mt-1.5 flex justify-between gap-3 text-[0.8rem] text-[var(--foreground)]">
                  <span>{viewer.exportSnapshot.progress_percent ?? 0}%</span>
                  <span className="text-[var(--muted)]">{viewer.exportEtaText}</span>
                </div>
                <div className="export-progress-wrapper">
                  <div className="export-progress-track">
                    {(viewer.exportSnapshot.status === "running" ||
                      viewer.exportSnapshot.progress_percent) &&
                    (viewer.exportSnapshot.progress_percent ?? 0) > 0 ? (
                      <>
                        <div
                          className="export-progress-fill-group"
                          style={{
                            width: `${viewer.exportSnapshot.progress_percent ?? 0}%`,
                          }}
                        >
                          <div className="export-progress-fill-ambient" />
                          <div className="export-progress-fill" />
                        </div>
                        {viewer.exportSnapshot.status === "running" ? (
                          <div
                            className="export-progress-glow-layer"
                            style={{
                              width: `${viewer.exportSnapshot.progress_percent ?? 0}%`,
                            }}
                          >
                            <span className="export-progress-glow-beam" aria-hidden="true" />
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </header>

      <SegmentVirtualGrid
        segments={viewer.visibleSegments}
        scriptFormat={viewer.scriptFormat}
        customQueries={viewer.customQueries}
        loadingIds={viewer.loadingIds}
        focusedSegmentId={viewer.focusedSegmentId}
        onCustomQueryChange={handleCustomQueryChange}
        onFetch={handleFetch}
        onSelectAlternative={handleSelectAlternative}
        onChooseFromStorage={handleChooseFromStorage}
        onFlagClip={handleFlagClip}
      />

      <StorageClipSelectModal
        segment={storagePickerSegment}
        busy={storagePickerBusy}
        onClose={() => {
          if (!storagePickerBusy) setStoragePickerSegmentId(null);
        }}
        onConfirm={(payload) => void handleConfirmStorageClip(payload)}
      />

      <FolderFetchModal
        open={folderFetchOpen}
        busy={folderFetchBusy}
        plan={folderFetchPlan}
        error={folderFetchError}
        onClose={() => {
          if (!folderFetchBusy) {
            setFolderFetchOpen(false);
            setFolderFetchPlan(null);
            setFolderFetchError(null);
          }
        }}
        onConfirm={(strategy) => void handleConfirmFolderFetch(strategy)}
        onReload={(strategy) => void reloadFolderFetch(strategy)}
      />

      <FlagClipModal
        open={viewer.flagConflict !== null}
        affectedCount={viewer.flagConflict?.affectedCount ?? 0}
        segmentIds={viewer.flagConflict?.segmentIds ?? []}
        onRefetchAffected={() => void viewer.refetchFlagConflictSegments("mix")}
        onLeaveAsIs={viewer.dismissFlagConflict}
      />

      <ExportAudioModal
        open={exportConfirmOpen}
        selectedCount={viewer.selectedCount}
        totalSegments={viewer.segments.length}
        onClose={() => setExportConfirmOpen(false)}
        onConfirm={async (options) => {
          setExportConfirmOpen(false);
          await viewer.startExport(options);
          router.push("/progress");
        }}
      />

      <AnimatePresence>
        {viewer.statusMessage ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            className={`fixed bottom-4 right-4 z-50 max-w-[360px] rounded-xl px-3.5 py-3 text-sm ${
              viewer.statusIsError ? "glow-toast glow-toast-error" : "glow-toast"
            }`}
          >
            {viewer.statusMessage}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
