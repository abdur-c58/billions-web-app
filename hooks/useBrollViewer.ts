"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch, isRetryableFetchError, resolveBrollApiUrl, retryDelayMs, sleep } from "@/lib/api";
import { regenerateThumbnailPrompts, regenerateYoutubeDescription } from "@/lib/export";
import { formatDuration, truncateExportMessage } from "@/lib/format";
import { findSegmentAtExportTime, formatTimestampClock, parseTimestamp } from "@/lib/timestamp";
import type {
  AiJudgeStatus,
  ExportSnapshot,
  FetchPayload,
  FlagClipResponse,
  FolderFetchPlan,
  FolderShortageStrategy,
  JudgmentSummary,
  RemotionPreviewResponse,
  RemotionPropsSaveResponse,
  RemotionSuggestResponse,
  ScriptFormat,
  SegmentsPayload,
  TimestampAlignment,
  ViewerSegment,
} from "@/lib/types";
import { getSessionHeaders } from "@/lib/session";
import { computeQualityTier, summarizeJudgments, type QualityTier } from "@/lib/judgment";
import {
  isRemotionSegment,
  segmentCountsAsReady,
  segmentNeedsBrollFetch,
} from "@/lib/remotion";
import { STATUS_POLL_MS, usePolling } from "@/hooks/usePolling";

const EXPORT_POLL_MS = 2000;

const BATCH_DELAY_MS = 250;
const BATCH_PASS_DELAY_MS = 3000;
const MAX_FETCH_ATTEMPTS = 50;
const DEFAULT_FETCH_CONCURRENCY = 2;

type StatusFilter = "" | "missing" | "selected";
type QualityFilter = "" | QualityTier;

export type BatchProgress = {
  label: string;
  pass: number;
  done: number;
  total: number;
  status: "fetching" | "waiting";
  waitSeconds?: number;
};

export type FetchProvider = "mix" | "pexels" | "pixabay" | "random";

export function useBrollViewer() {
  const [segments, setSegments] = useState<ViewerSegment[]>([]);
  const [title, setTitle] = useState("Loading script…");
  const [projectFolder, setProjectFolder] = useState("");
  const [scriptFormat, setScriptFormat] = useState<ScriptFormat>("legacy");
  const [videoDurationS, setVideoDurationS] = useState<number | null>(null);
  const [timestampAlignment, setTimestampAlignment] = useState<TimestampAlignment | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [beatFilter, setBeatFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [qualityFilter, setQualityFilter] = useState<QualityFilter>("");
  const [aiJudge, setAiJudge] = useState<AiJudgeStatus>({ enabled: false });
  const [customQueries, setCustomQueries] = useState<Record<number, string>>({});
  const [loadingIds, setLoadingIds] = useState<Set<number>>(new Set());
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [exportRunning, setExportRunning] = useState(false);
  const [exportSnapshot, setExportSnapshot] = useState<ExportSnapshot>({
    status: "idle",
  });
  const [exportInputsHash, setExportInputsHash] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusIsError, setStatusIsError] = useState(false);
  const [backendReady, setBackendReady] = useState(true);
  const [fetchConcurrency, setFetchConcurrency] = useState(DEFAULT_FETCH_CONCURRENCY);
  const [focusedSegmentId, setFocusedSegmentId] = useState<number | null>(null);
  const [timestampSeekInput, setTimestampSeekInput] = useState("");
  const [flagConflict, setFlagConflict] = useState<{
    segmentIds: number[];
    affectedCount: number;
  } | null>(null);
  const [remotionPreviewUrls, setRemotionPreviewUrls] = useState<Record<number, string>>({});
  const [remotionBusyIds, setRemotionBusyIds] = useState<Set<number>>(new Set());

  const batchRunningRef = useRef(false);
  const exportHashTimerRef = useRef<number | null>(null);
  const statusTimerRef = useRef<number | null>(null);
  const batchAbortRef = useRef(false);
  const customQueriesRef = useRef(customQueries);
  const segmentsRef = useRef(segments);
  const videoDurationRef = useRef(videoDurationS);
  const scriptFormatRef = useRef(scriptFormat);
  const remotionBlobUrlsRef = useRef<Record<number, string>>({});

  useEffect(() => {
    customQueriesRef.current = customQueries;
  }, [customQueries]);

  useEffect(() => {
    segmentsRef.current = segments;
  }, [segments]);

  useEffect(() => {
    videoDurationRef.current = videoDurationS;
  }, [videoDurationS]);

  useEffect(() => {
    scriptFormatRef.current = scriptFormat;
  }, [scriptFormat]);

  useEffect(() => {
    return () => {
      for (const url of Object.values(remotionBlobUrlsRef.current)) {
        URL.revokeObjectURL(url);
      }
    };
  }, []);

  const showStatus = useCallback((message: string, isError = false) => {
    setStatusMessage(message);
    setStatusIsError(isError);
    if (statusTimerRef.current) {
      window.clearTimeout(statusTimerRef.current);
    }
    statusTimerRef.current = window.setTimeout(() => setStatusMessage(null), 4000);
  }, []);

  const beats = useMemo(() => {
    return [...new Set(segments.map((segment) => segment.beat))].sort((a, b) => a - b);
  }, [segments]);

  const visibleSegments = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return segments.filter((segment) => {
      if (beatFilter && String(segment.beat) !== beatFilter) return false;
      if (statusFilter === "missing" && segmentCountsAsReady(segment)) return false;
      if (statusFilter === "selected" && !segmentCountsAsReady(segment)) return false;
      if (qualityFilter) {
        const tier =
          segment.selection?.quality_tier ?? computeQualityTier(segment.selection);
        if (tier !== qualityFilter) return false;
      }
      if (!query) return true;

      const haystack = [
        segment.segment_id,
        segment.beat,
        segment.label,
        segment.content,
        segment.description,
        segment.search_query,
        segment.category,
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(query);
    });
  }, [segments, searchQuery, beatFilter, statusFilter, qualityFilter]);

  const judgmentSummary = useMemo<JudgmentSummary>(
    () => summarizeJudgments(segments),
    [segments],
  );

  const selectedCount = segments.filter((segment) => segmentCountsAsReady(segment)).length;

  const updateExportUi = useCallback((snapshot: ExportSnapshot) => {
    setExportSnapshot(snapshot);
    setExportRunning(snapshot.status === "running");
  }, []);

  const refreshExportInputsHash = useCallback(async () => {
    try {
      const payload = await apiFetch<{ export_inputs_hash: string }>("/api/export/inputs-hash");
      setExportInputsHash(payload.export_inputs_hash);
    } catch {
      // Non-fatal — keep existing hash.
    }
  }, []);

  const pollExportStatus = useCallback(async () => {
    try {
      const snapshot = await apiFetch<ExportSnapshot>("/api/export/status");
      updateExportUi(snapshot);
      if (snapshot.status === "done" && snapshot.inputs_hash) {
        setExportInputsHash(snapshot.inputs_hash);
      }
    } catch (error) {
      showStatus(error instanceof Error ? error.message : "Export status failed", true);
    }
  }, [showStatus, updateExportUi]);

  const regenerateDescription = useCallback(
    async (includeEmojis: boolean, includeChapters: boolean) => {
      const snapshot = await regenerateYoutubeDescription(includeEmojis, includeChapters);
      updateExportUi(snapshot);
      if (snapshot.status === "done" && snapshot.inputs_hash) {
        setExportInputsHash(snapshot.inputs_hash);
      }
      return (snapshot.youtube_description || "").trim();
    },
    [updateExportUi],
  );

  const regenerateThumbnails = useCallback(async () => {
    const snapshot = await regenerateThumbnailPrompts();
    updateExportUi(snapshot);
    return snapshot.thumbnail_prompts || [];
  }, [updateExportUi]);

  const loadSegments = useCallback(async () => {
    const payload = await apiFetch<SegmentsPayload>("/api/segments");
    setSegments(payload.segments || []);
    setVideoDurationS(
      typeof payload.video_duration_s === "number" ? payload.video_duration_s : null,
    );
    setTimestampAlignment(payload.timestamp_alignment ?? null);
    if (payload.ai_judge) {
      setAiJudge(payload.ai_judge);
    }
    setScriptFormat(payload.script_format === "folder" ? "folder" : "legacy");
    setExportInputsHash(payload.export_inputs_hash ?? null);
    setTitle(payload.title || "Billions");
    setProjectFolder(
      payload.project_folder
        ? `Project: ${payload.project_folder} · ${payload.segments?.length ?? 0} segments`
        : `${payload.segments?.length ?? 0} segments`,
    );
  }, []);

  const checkServerHealth = useCallback(async () => {
    try {
      const health = await apiFetch<{
        features?: string[];
        export_api_version?: number;
        export_mux_mode?: string;
        ai_judge?: AiJudgeStatus;
        pexels_key_count?: number;
        fetch_concurrency?: number;
        pixabay_enabled?: boolean;
        provider_modes?: FetchProvider[];
      }>("/api/health");
      if (!health.features?.includes("export")) {
        throw new Error("Server is missing export support.");
      }
      if (health.export_api_version !== undefined && health.export_api_version < 3) {
        throw new Error(
          "Export API is outdated. Restart backend: npm run dev:api",
        );
      }
      if (health.ai_judge) {
        setAiJudge(health.ai_judge);
      }
      const concurrency =
        health.fetch_concurrency ?? health.pexels_key_count ?? DEFAULT_FETCH_CONCURRENCY;
      setFetchConcurrency(Math.max(1, concurrency));
      setBackendReady(true);
    } catch (error) {
      setBackendReady(false);
      showStatus(
        error instanceof Error
          ? `${error.message} Start backend: npm run dev:api`
          : "Cannot reach broll viewer API.",
        true,
      );
    }
  }, [showStatus]);

  const applyFetchPayload = useCallback((segmentId: number, payload: FetchPayload) => {
    setSegments((current) =>
      current.map((segment) =>
        segment.segment_id === segmentId
          ? {
              ...segment,
              selection: payload.selection,
              _alternatives: payload.alternatives,
            }
          : segment,
      ),
    );
    if (payload.selection?.custom_query) {
      setCustomQueries((current) => ({
        ...current,
        [segmentId]: payload.selection.custom_query || "",
      }));
    }
  }, []);

  const fetchSegmentOnce = useCallback(
    async (segmentId: number, refetch: boolean, provider: FetchProvider) => {
    const customQuery = (customQueriesRef.current[segmentId] || "").trim();
      let url = `/api/fetch?segment_id=${segmentId}&refetch=${refetch ? "true" : "false"}&provider=${provider}`;
    if (customQuery) {
      url += `&query=${encodeURIComponent(customQuery)}`;
    }
    const payload = await apiFetch<FetchPayload>(url);
    applyFetchPayload(segmentId, payload);
    return payload;
    },
    [applyFetchPayload],
  );

  const fetchSegmentWithRetry = useCallback(
    async (
      segmentId: number,
      refetch: boolean,
      quiet = false,
      provider: FetchProvider = "mix",
    ) => {
      const segment = segmentsRef.current.find((item) => item.segment_id === segmentId);
      if (segment && isRemotionSegment(segment)) {
        if (!quiet) {
          showStatus(`Segment ${segmentId} uses Remotion — no b-roll fetch needed.`);
        }
        return true;
      }
      if (segment && scriptFormatRef.current === "folder") {
        const category = segment.category.trim().toLowerCase();
        if (category !== "stock") {
          const folderStatus = segment.folder_status;
          if (folderStatus && !folderStatus.has_folder) {
            const confirmed = window.confirm(
              `Segment ${segmentId} (type "${segment.category}") has no B-Roll/${segment.category}/ folder.\n\n` +
                `API fetch will use: "${segment.search_query || segment.description}".\n\nContinue?`,
            );
            if (!confirmed) return false;
          }
        }
      }

      setLoadingIds((current) => new Set(current).add(segmentId));

      try {
        for (let attempt = 1; attempt <= MAX_FETCH_ATTEMPTS; attempt += 1) {
          try {
            const payload = await fetchSegmentOnce(segmentId, refetch, provider);
            if (!quiet) {
              const label = payload.query_used || payload.search_query;
              const tier =
                payload.selection?.quality_label ||
                payload.selection?.quality_tier ||
                "unknown";
              showStatus(
                `Segment ${segmentId}: ${refetch ? "refetched" : "loaded"} (${provider}) "${label}" · ${tier}`,
              );
            }
            return true;
          } catch (error) {
            if (attempt >= MAX_FETCH_ATTEMPTS) {
              if (!quiet) {
                showStatus(
                  `Segment ${segmentId} failed after ${MAX_FETCH_ATTEMPTS} attempts: ${
                    error instanceof Error ? error.message : "Unknown error"
                  }`,
                  true,
                );
              }
              return false;
            }

            const delay = isRetryableFetchError(error)
              ? retryDelayMs(attempt, error)
              : 1200 * attempt;

            if (!quiet) {
              showStatus(
                `Segment ${segmentId} retry ${attempt}/${MAX_FETCH_ATTEMPTS} in ${Math.round(delay / 1000)}s…`,
              );
            }
            await sleep(delay);
          }
        }
        return false;
      } finally {
        setLoadingIds((current) => {
          const next = new Set(current);
          next.delete(segmentId);
          return next;
        });
      }
    },
    [fetchSegmentOnce, showStatus],
  );

  const selectAlternative = useCallback(
    async (segmentId: number, searchQueryValue: string, videoIndex: number) => {
      const segment = segments.find((item) => item.segment_id === segmentId);
      const video = segment?._alternatives?.[videoIndex];
      if (!video) return;

      try {
        const payload = await apiFetch<{ selection: ViewerSegment["selection"] }>(
          "/api/select",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              segment_id: segmentId,
              search_query: searchQueryValue,
              video,
              page: 1,
              result_index: videoIndex,
            }),
          },
        );

        setSegments((current) =>
          current.map((item) =>
            item.segment_id === segmentId
              ? { ...item, selection: payload.selection }
              : item,
          ),
        );
        showStatus(`Segment ${segmentId}: selected clip ${videoIndex + 1}`);
      } catch (error) {
        showStatus(error instanceof Error ? error.message : "Select failed", true);
      }
    },
    [segments, showStatus],
  );

  const selectStorageClip = useCallback(
    async (
      segmentId: number,
      searchQueryValue: string,
      payload: {
        storageKey: string;
        name: string;
        duration: number | null;
        loop: boolean;
      },
    ) => {
      try {
        const response = await apiFetch<{ selection: ViewerSegment["selection"] }>(
          "/api/select/storage",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              segment_id: segmentId,
              search_query: searchQueryValue,
              storage_key: payload.storageKey,
              duration: payload.duration,
              loop: payload.loop,
              name: payload.name,
            }),
          },
        );

        setSegments((current) =>
          current.map((item) =>
            item.segment_id === segmentId
              ? { ...item, selection: response.selection, _alternatives: [] }
              : item,
          ),
        );
        showStatus(
          payload.loop
            ? `Segment ${segmentId}: using storage clip with loop`
            : `Segment ${segmentId}: selected storage clip`,
        );
      } catch (error) {
        showStatus(error instanceof Error ? error.message : "Storage select failed", true);
        throw error;
      }
    },
    [showStatus],
  );

  const runBatchWorkers = useCallback(
    async (
      label: string,
      pass: number,
      targetSegments: ViewerSegment[],
      refetch: boolean,
      provider: FetchProvider,
      concurrency: number,
      onProgress: (done: number, total: number, segmentId: number) => void,
    ) => {
      const failed: ViewerSegment[] = [];
      let nextIndex = 0;
      let completed = 0;
      const workerCount = Math.min(concurrency, targetSegments.length);

      const worker = async () => {
        while (!batchAbortRef.current) {
          const index = nextIndex;
          nextIndex += 1;
          if (index >= targetSegments.length) return;

          const segment = targetSegments[index];
          const ok = await fetchSegmentWithRetry(segment.segment_id, refetch, true, provider);
          if (!ok) failed.push(segment);

          completed += 1;
          onProgress(completed, targetSegments.length, segment.segment_id);

          if (index < targetSegments.length - 1) {
            await sleep(BATCH_DELAY_MS);
          }
        }
      };

      await Promise.all(Array.from({ length: workerCount }, () => worker()));
      return failed;
    },
    [fetchSegmentWithRetry],
  );

  const runBatch = useCallback(
    async (
      label: string,
      getTargets: () => ViewerSegment[],
      refetch: boolean,
      provider: FetchProvider,
      options?: { untilComplete?: boolean },
    ) => {
      if (batchRunning) return;

      const initialTargets = getTargets();
      if (!initialTargets.length) {
        showStatus(`No segments to ${label.toLowerCase()}.`);
        return;
      }

      batchAbortRef.current = false;
      setBatchRunning(true);
      let pass = 0;

      const reportProgress = (
        pendingTotal: number,
        done: number,
        currentPass: number,
        status: BatchProgress["status"] = "fetching",
        waitSeconds?: number,
      ) => {
        setBatchProgress({
          label,
          pass: currentPass,
          done,
          total: pendingTotal,
          status,
          waitSeconds,
        });
      };

      try {
        if (options?.untilComplete) {
          while (!batchAbortRef.current) {
            const pending = getTargets();
            if (!pending.length) break;

            pass += 1;
            const beforeCount = pending.length;

            reportProgress(pending.length, 0, pass);

            const failed = await runBatchWorkers(
              label,
              pass,
              pending,
              refetch,
              provider,
              fetchConcurrency,
              (done, total, segmentId) => {
                reportProgress(total, done, pass);
                showStatus(
                  `${label} pass ${pass} — ${done}/${total} — segment ${segmentId}`,
                );
              },
            );

            if (batchAbortRef.current) break;

            const afterCount = getTargets().length;
            const succeeded = Math.max(0, beforeCount - afterCount);

            if (afterCount === 0) break;

            const waitMs =
              succeeded === 0
                ? Math.min(120000, BATCH_PASS_DELAY_MS * pass * 2)
                : BATCH_PASS_DELAY_MS;
            const waitSeconds = Math.round(waitMs / 1000);
            reportProgress(afterCount, 0, pass + 1, "waiting", waitSeconds);
            showStatus(
              `${label}: ${afterCount} still missing — pass ${pass + 1} in ${waitSeconds}s…`,
            );
            await sleep(waitMs);

            if (failed.length === 0 && afterCount > 0) {
              continue;
            }
          }
        } else {
          let pending = [...initialTargets];

          while (pending.length > 0 && !batchAbortRef.current) {
            pass += 1;

            reportProgress(pending.length, 0, pass);

            const failed = await runBatchWorkers(
              label,
              pass,
              pending,
              refetch,
              provider,
              fetchConcurrency,
              (done, total, segmentId) => {
                reportProgress(total, done, pass);
                showStatus(
                  `${label} pass ${pass} — ${done}/${total} — segment ${segmentId}`,
                );
              },
            );

            if (batchAbortRef.current) break;
            if (!failed.length) break;

            pending = failed;
            const waitMs = Math.min(90000, BATCH_PASS_DELAY_MS * pass);
            const waitSeconds = Math.round(waitMs / 1000);
            reportProgress(failed.length, 0, pass + 1, "waiting", waitSeconds);
            showStatus(
              `${label}: ${failed.length} failed — retry pass ${pass + 1} in ${waitSeconds}s…`,
            );
            await sleep(waitMs);
          }
        }
      } finally {
        setBatchRunning(false);
        setBatchProgress(null);
      }

      const remaining = options?.untilComplete ? getTargets().length : 0;

      if (batchAbortRef.current) {
        showStatus(`${label} cancelled.`);
      } else if (options?.untilComplete && remaining > 0) {
        showStatus(
          `${label} stopped with ${remaining} segment(s) still missing.`,
          true,
        );
      } else if (!options?.untilComplete && pass > 0) {
        showStatus(`Finished ${label.toLowerCase()} — all targeted segments processed.`);
      } else if (options?.untilComplete) {
        showStatus(`Finished ${label.toLowerCase()} — all segments have b-roll.`);
      }
    },
    [batchRunning, fetchConcurrency, runBatchWorkers, showStatus],
  );

  const shouldApiFetchSegment = useCallback((segment: ViewerSegment) => {
    if (scriptFormatRef.current !== "folder") return true;
    const category = segment.category.trim().toLowerCase();
    if (category === "stock") return true;
    const folderFetchStarted = segmentsRef.current.some(
      (item) =>
        item.category.trim().toLowerCase() !== "stock" &&
        item.selection?.provider === "storage",
    );
    return folderFetchStarted;
  }, []);

  const fetchMissing = useCallback(async () => {
    await runBatch(
      "Fetching missing",
      () =>
        segmentsRef.current.filter(
          (segment) =>
            segmentNeedsBrollFetch(segment) && shouldApiFetchSegment(segment),
        ),
      false,
      "mix",
      { untilComplete: true },
    );
  }, [runBatch, shouldApiFetchSegment]);

  const loadFolderFetchPreview = useCallback(async (shortageStrategy?: FolderShortageStrategy) => {
    const query = shortageStrategy
      ? `?shortage_strategy=${encodeURIComponent(shortageStrategy)}`
      : "";
    return apiFetch<FolderFetchPlan>(`/api/folder-fetch/preview${query}`);
  }, []);

  const applyFolderFetch = useCallback(
    async (shortageStrategy?: FolderShortageStrategy) => {
      const result = await apiFetch<{
        applied_count: number;
        api_fetched_count?: number;
        applied: Array<{ segment_id: number; selection: ViewerSegment["selection"] }>;
        api_fetched?: Array<{ segment_id: number; selection?: ViewerSegment["selection"] }>;
        summary?: FolderFetchPlan["summary"];
      }>("/api/folder-fetch/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          shortageStrategy ? { shortage_strategy: shortageStrategy } : {},
        ),
      });

      const appliedById = new Map<number, ViewerSegment["selection"]>();
      for (const entry of result.applied ?? []) {
        if (entry.selection) appliedById.set(entry.segment_id, entry.selection);
      }
      for (const entry of result.api_fetched ?? []) {
        if (entry.selection) appliedById.set(entry.segment_id, entry.selection);
      }

      if (appliedById.size > 0) {
        setSegments((current) =>
          current.map((segment) => {
            const selection = appliedById.get(segment.segment_id);
            return selection ? { ...segment, selection, _alternatives: [] } : segment;
          }),
        );
      }

      const apiRemaining =
        (result.summary?.api ?? 0) +
        (result.summary?.api_warning ?? 0) +
        (result.summary?.unassigned ?? 0);
      const apiFetched = result.api_fetched_count ?? 0;
      showStatus(
        `Folder fetch assigned ${result.applied_count} clip${
          result.applied_count === 1 ? "" : "s"
        }` +
          (apiFetched > 0
            ? ` · ${apiFetched} fetched from API`
            : "") +
          (apiRemaining > 0
            ? ` · ${apiRemaining} still need attention`
            : ""),
      );
      return result;
    },
    [showStatus],
  );

  const refetchAll = useCallback(async (provider: FetchProvider = "mix") => {
    const targets = segmentsRef.current.filter((segment) => !isRemotionSegment(segment));
    if (!targets.length) return;
    const skipped = segmentsRef.current.length - targets.length;
    const confirmed = window.confirm(
      `Refetch all ${targets.length} b-roll segment${targets.length === 1 ? "" : "s"} using ${provider}?` +
        (skipped > 0
          ? ` (${skipped} Remotion segment${skipped === 1 ? "" : "s"} skipped)`
          : ""),
    );
    if (!confirmed) return;

    const snapshot = [...targets];
    await runBatch("Refetching", () => snapshot, true, provider);
  }, [runBatch]);

  const refetchReview = useCallback(
    async (provider: FetchProvider = "mix") => {
      const reviewTargets = segmentsRef.current.filter((segment) => {
        if (isRemotionSegment(segment)) return false;
        const tier = segment.selection?.quality_tier ?? computeQualityTier(segment.selection);
        return tier === "review";
      });
      await runBatch("Refetching review clips", () => reviewTargets, true, provider);
    },
    [runBatch],
  );

  const refetchUnscored = useCallback(
    async () => {
      const unscoredCount = segmentsRef.current.filter((segment) => {
        if (isRemotionSegment(segment)) return false;
        const selection = segment.selection;
        return Boolean(selection?.url) && !selection?.confidence_source;
      }).length;
      if (!unscoredCount) {
        showStatus("No unscored clips found.");
        return;
      }

      setBatchRunning(true);
      setBatchProgress({
        label: "Rescoring unscored clips",
        pass: 1,
        done: 0,
        total: unscoredCount,
        status: "fetching",
      });
      try {
        const payload = await apiFetch<{ updated: number }>("/api/rescore/unscored", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ai: true }),
        });
        await loadSegments();
        showStatus(`Rescored ${payload.updated ?? 0} unscored clip(s).`);
      } catch (error) {
        showStatus(error instanceof Error ? error.message : "Rescore failed", true);
      } finally {
        setBatchProgress(null);
        setBatchRunning(false);
      }
    },
    [loadSegments, showStatus],
  );

  const startExport = useCallback(async (options?: {
    backgroundAudio?: string | null;
    mixAdjustments?: { narration_adjust_db: number; background_adjust_db: number };
    resolution?: string;
    quality?: string;
    includeSubtitles?: boolean;
  }) => {
    const backgroundAudio = options?.backgroundAudio ?? null;
    const mixAdjustments = options?.mixAdjustments ?? {
      narration_adjust_db: 0,
      background_adjust_db: 0,
    };
    const resolution = options?.resolution ?? "4k";
    const quality = options?.quality ?? "balanced";
    const includeSubtitles = Boolean(options?.includeSubtitles);
    try {
      const snapshot = await apiFetch<ExportSnapshot>("/api/export/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          background_audio: backgroundAudio,
          narration_adjust_db: mixAdjustments.narration_adjust_db,
          background_adjust_db: mixAdjustments.background_adjust_db,
          resolution,
          quality,
          include_subtitles: includeSubtitles,
        }),
      });
      updateExportUi(snapshot);
      showStatus(
        backgroundAudio
          ? `Export started with background: ${backgroundAudio}`
          : "Export started…",
      );
      void pollExportStatus();
    } catch (error) {
      showStatus(error instanceof Error ? error.message : "Export failed", true);
    }
  }, [
    pollExportStatus,
    showStatus,
    updateExportUi,
  ]);

  const cancelExport = useCallback(async () => {
    try {
      const snapshot = await apiFetch<ExportSnapshot>("/api/export/cancel", {
        method: "POST",
      });
      updateExportUi(snapshot);
      showStatus("Export cancelled");
    } catch (error) {
      showStatus(error instanceof Error ? error.message : "Cancel failed", true);
    }
  }, [showStatus, updateExportUi]);

  const flagClip = useCallback(
    async (segmentId: number) => {
      try {
        const payload = await apiFetch<FlagClipResponse>("/api/flagged", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ segment_id: segmentId }),
        });
        await loadSegments();
        if (payload.affected_count > 1) {
          setFlagConflict({
            segmentIds: payload.affected_segment_ids,
            affectedCount: payload.affected_count,
          });
        } else {
          showStatus("Clip flagged — excluded from future fetches");
        }
      } catch (error) {
        showStatus(error instanceof Error ? error.message : "Flag failed", true);
      }
    },
    [loadSegments, showStatus],
  );

  const dismissFlagConflict = useCallback(() => {
    setFlagConflict(null);
    showStatus("Flagged for future fetches only — current selections unchanged");
  }, [showStatus]);

  const resolveRemotionPreviewPlayback = useCallback(async (segmentId: number, apiPath: string) => {
    const fetchUrl = await resolveBrollApiUrl(apiPath);
    const response = await fetch(fetchUrl, { headers: getSessionHeaders() });
    if (!response.ok) {
      let message = "Remotion preview unavailable";
      try {
        const payload = (await response.json()) as { error?: string };
        if (payload.error) message = payload.error;
      } catch {
        // Response was not JSON.
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    if (!blob.size) {
      throw new Error("Remotion preview is empty");
    }

    const playbackBlob =
      blob.type === "video/mp4" ? blob : new Blob([blob], { type: "video/mp4" });
    const objectUrl = URL.createObjectURL(playbackBlob);
    const prior = remotionBlobUrlsRef.current[segmentId];
    if (prior) {
      URL.revokeObjectURL(prior);
    }
    remotionBlobUrlsRef.current[segmentId] = objectUrl;
    setRemotionPreviewUrls((current) => ({ ...current, [segmentId]: objectUrl }));
    return objectUrl;
  }, []);

  const saveRemotionProps = useCallback(
    async (segmentId: number, props: Record<string, unknown>) => {
      setRemotionBusyIds((current) => new Set(current).add(segmentId));
      try {
        const payload = await apiFetch<RemotionPropsSaveResponse>("/api/remotion/props", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ segment_id: segmentId, props }),
        });
        setSegments((current) =>
          current.map((segment) =>
            segment.segment_id === segmentId
              ? {
                  ...segment,
                  remotion: {
                    composition: payload.remotion.composition,
                    props: payload.remotion.props ?? {},
                  },
                }
              : segment,
          ),
        );
        if (payload.export_inputs_hash) {
          setExportInputsHash(payload.export_inputs_hash);
        }
        showStatus(`Segment ${segmentId}: motion settings saved`);
      } catch (error) {
        showStatus(
          error instanceof Error ? error.message : "Failed to save motion settings",
          true,
        );
        throw error;
      } finally {
        setRemotionBusyIds((current) => {
          const next = new Set(current);
          next.delete(segmentId);
          return next;
        });
      }
    },
    [showStatus],
  );

  const previewRemotion = useCallback(
    async (segmentId: number, props: Record<string, unknown>) => {
      setRemotionBusyIds((current) => new Set(current).add(segmentId));
      try {
        const payload = await apiFetch<RemotionPreviewResponse>("/api/remotion/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ segment_id: segmentId, props }),
        });
        await resolveRemotionPreviewPlayback(segmentId, payload.preview_url);
        showStatus(`Segment ${segmentId}: motion preview ready`);
      } catch (error) {
        showStatus(
          error instanceof Error ? error.message : "Remotion preview failed",
          true,
        );
        throw error;
      } finally {
        setRemotionBusyIds((current) => {
          const next = new Set(current);
          next.delete(segmentId);
          return next;
        });
      }
    },
    [resolveRemotionPreviewPlayback, showStatus],
  );

  const suggestRemotionPrompt = useCallback(
    async (
      segmentId: number,
      prompt: string,
      currentProps: Record<string, unknown>,
    ) => {
      setRemotionBusyIds((current) => new Set(current).add(segmentId));
      try {
        const payload = await apiFetch<RemotionSuggestResponse>("/api/remotion/suggest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            segment_id: segmentId,
            prompt,
            current_props: currentProps,
          }),
        });
        if (payload.ai_judge) {
          setAiJudge(payload.ai_judge);
        }
        const summary = payload.summary || "Prompt applied.";
        showStatus(
          payload.ai_used
            ? `Segment ${segmentId}: ${summary}`
            : `Segment ${segmentId}: ${summary}`,
        );
        return {
          props: payload.props,
          summary,
        };
      } catch (error) {
        showStatus(
          error instanceof Error ? error.message : "Could not apply motion prompt",
          true,
        );
        throw error;
      } finally {
        setRemotionBusyIds((current) => {
          const next = new Set(current);
          next.delete(segmentId);
          return next;
        });
      }
    },
    [showStatus],
  );

  const refetchFlagConflictSegments = useCallback(
    async (provider: FetchProvider = "mix") => {
      const targets = flagConflict?.segmentIds ?? [];
      setFlagConflict(null);
      if (!targets.length) return;

      const snapshot = [...targets];
      const label = "Refetching flagged segments";
      await runBatch(
        label,
        () =>
          segmentsRef.current.filter(
            (segment) =>
              snapshot.includes(segment.segment_id) && !isRemotionSegment(segment),
          ),
        true,
        provider,
      );
      showStatus(`Refetched ${snapshot.length} segment(s) after flagging`);
    },
    [flagConflict, runBatch, showStatus],
  );

  const seekToTimestamp = useCallback(
    (rawInput?: string) => {
      const raw = (rawInput ?? timestampSeekInput).trim();
      if (!raw) {
        showStatus("Enter a timestamp from the exported video (e.g. 1:23)", true);
        return;
      }

      const seconds = parseTimestamp(raw);
      if (seconds == null) {
        showStatus("Invalid timestamp. Use 1:23, 1:02:03, or 83.5", true);
        return;
      }

      const match = findSegmentAtExportTime(
        segmentsRef.current,
        seconds,
        videoDurationRef.current,
      );
      if (!match) {
        showStatus("No segment found for that timestamp", true);
        return;
      }

      const segment = match.segment;
      setSearchQuery("");
      setBeatFilter("");
      setStatusFilter("");
      setQualityFilter("");
      setFocusedSegmentId(segment.segment_id);
      setTimestampSeekInput(formatTimestampClock(seconds));

      showStatus(
        `Segment ${segment.segment_id} · export ${formatTimestampClock(match.exportStart)}–${formatTimestampClock(match.exportEnd)}`,
      );
    },
    [showStatus, timestampSeekInput],
  );

  useEffect(() => {
    if (focusedSegmentId == null) return;

    const clearHighlight = window.setTimeout(() => {
      setFocusedSegmentId((current) => (current === focusedSegmentId ? null : current));
    }, 6000);

    return () => {
      window.clearTimeout(clearHighlight);
    };
  }, [focusedSegmentId]);

  useEffect(() => {
    if (!segments.length) return;
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("segment");
    if (!raw) return;
    const id = Number.parseInt(raw, 10);
    if (!Number.isFinite(id)) return;
    if (!segments.some((segment) => segment.segment_id === id)) return;
    setFocusedSegmentId(id);
  }, [segments]);

  useEffect(() => {
    if (segments.length === 0) return;

    if (exportHashTimerRef.current) {
      window.clearTimeout(exportHashTimerRef.current);
    }
    exportHashTimerRef.current = window.setTimeout(() => {
      void apiFetch<{ export_inputs_hash: string }>("/api/export/inputs-hash")
        .then((payload) => setExportInputsHash(payload.export_inputs_hash))
        .catch(() => {});
    }, 250);

    return () => {
      if (exportHashTimerRef.current) {
        window.clearTimeout(exportHashTimerRef.current);
      }
    };
  }, [segments]);

  const hasCompletedExport = useMemo(
    () => exportSnapshot.status === "done",
    [exportSnapshot.status],
  );

  const exportUnchanged = useMemo(() => {
    if (!hasCompletedExport || !exportSnapshot.inputs_hash || !exportInputsHash) {
      return false;
    }
    return exportInputsHash === exportSnapshot.inputs_hash;
  }, [exportInputsHash, exportSnapshot.inputs_hash, hasCompletedExport]);

  const exportButtonLabel = hasCompletedExport ? "Re-Export" : "Export final video";

  const exportDisabledReason = exportUnchanged
    ? "No changes since the last export. Update clip selections or timestamps first."
    : null;

  batchRunningRef.current = batchRunning;

  useEffect(() => {
    void loadSegments()
      .then(() => checkServerHealth())
      .then(() => pollExportStatus())
      .catch((error) => {
        showStatus(error instanceof Error ? error.message : "Failed to load", true);
      });

    return () => {
      if (statusTimerRef.current) window.clearTimeout(statusTimerRef.current);
    };
  }, [checkServerHealth, loadSegments, pollExportStatus, showStatus]);

  usePolling(async () => {
    if (!batchRunningRef.current) {
      await loadSegments();
    }
  }, STATUS_POLL_MS);

  usePolling(() => pollExportStatus(), EXPORT_POLL_MS);

  const exportProgressText = useMemo(() => {
    const snapshot = exportSnapshot;
    if (snapshot.status === "idle") {
      return "Ready to export narration + selected b-roll (GPU encoding).";
    }
    if (snapshot.status === "running") {
      return `${snapshot.stage}: ${snapshot.message} (${snapshot.current}/${snapshot.total || "?"})`;
    }
    if (snapshot.status === "done") {
      return `Export complete${snapshot.encoder ? ` via ${snapshot.encoder}` : ""}`;
    }
    if (snapshot.status === "interrupted") {
      return snapshot.message || "Export was interrupted.";
    }
    if (snapshot.status === "error") {
      return `Export failed: ${truncateExportMessage(snapshot.error || snapshot.message)}`;
    }
    return snapshot.message || "";
  }, [exportSnapshot]);

  const exportEtaText = useMemo(() => {
    const snapshot = exportSnapshot;
    if (snapshot.status === "running") {
      const eta =
        snapshot.eta_seconds != null
          ? `ETA ${formatDuration(snapshot.eta_seconds)} remaining`
          : "Calculating ETA…";
      const elapsed = snapshot.elapsed_seconds
        ? ` · elapsed ${formatDuration(snapshot.elapsed_seconds)}`
        : "";
      return `${eta}${elapsed}`;
    }
    if (snapshot.status === "done" && snapshot.elapsed_seconds) {
      return `Finished in ${formatDuration(snapshot.elapsed_seconds)}`;
    }
    if (snapshot.status === "interrupted") {
      return "Start a new export to continue.";
    }
    return "";
  }, [exportSnapshot]);

  return {
    segments,
    visibleSegments,
    title,
    projectFolder,
    scriptFormat,
    timestampAlignment,
    searchQuery,
    setSearchQuery,
    beatFilter,
    setBeatFilter,
    statusFilter,
    setStatusFilter,
    qualityFilter,
    setQualityFilter,
    judgmentSummary,
    aiJudge,
    beats,
    customQueries,
    setCustomQueries,
    loadingIds,
    batchRunning,
    batchProgress,
    exportRunning,
    exportSnapshot,
    exportProgressText,
    exportEtaText,
    hasCompletedExport,
    exportUnchanged,
    exportButtonLabel,
    exportDisabledReason,
    selectedCount,
    statusMessage,
    statusIsError,
    backendReady,
    fetchConcurrency,
    fetchSegmentWithRetry,
    selectAlternative,
    selectStorageClip,
    loadFolderFetchPreview,
    applyFolderFetch,
    fetchMissing,
    refetchAll,
    refetchReview,
    refetchUnscored,
    startExport,
    cancelExport,
    regenerateDescription,
    regenerateThumbnails,
    flagClip,
    flagConflict,
    dismissFlagConflict,
    refetchFlagConflictSegments,
    remotionPreviewUrls,
    remotionBusyIds,
    saveRemotionProps,
    previewRemotion,
    suggestRemotionPrompt,
    focusedSegmentId,
    timestampSeekInput,
    setTimestampSeekInput,
    seekToTimestamp,
    loadSegments,
  };
}
