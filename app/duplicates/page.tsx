"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { apiFetch, isRetryableFetchError, retryDelayMs, sleep } from "@/lib/api";
import type { DuplicateClip, DuplicatesPayload } from "@/lib/types";

type FetchProvider = "mix" | "commons";

const REFETCH_DELAY_MS = 250;
const MAX_FETCH_ATTEMPTS = 3;

type BulkProgress = {
  label: string;
  done: number;
  total: number;
  currentSegmentId: number | null;
};

function formatGap(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rem = total % 60;
  if (minutes <= 0) return `${rem}s`;
  if (rem === 0) return `${minutes}m`;
  return `${minutes}m ${rem}s`;
}

/** Keep the first occurrence of each duplicate clip; refetch the rest. */
function segmentIdsToRefetch(clips: DuplicateClip[]): number[] {
  const ids = new Set<number>();
  for (const clip of clips) {
    const sorted = [...clip.segment_ids].sort((a, b) => a - b);
    for (const segmentId of sorted.slice(1)) {
      ids.add(segmentId);
    }
  }
  return [...ids].sort((a, b) => a - b);
}

export default function DuplicatesPage() {
  const [duplicates, setDuplicates] = useState<DuplicateClip[]>([]);
  const [summary, setSummary] = useState({ total_groups: 0, total_segments_affected: 0 });
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState<BulkProgress | null>(null);

  const loadDuplicates = useCallback(async () => {
    try {
      const payload = await apiFetch<DuplicatesPayload>("/api/duplicates");
      const nextDuplicates = payload.duplicates || [];
      setDuplicates(nextDuplicates);
      setSummary({
        total_groups: payload.total_groups ?? nextDuplicates.length,
        total_segments_affected: payload.total_segments_affected ?? 0,
      });
      setSelectedKeys((current) => {
        const valid = new Set(nextDuplicates.map((clip) => clip.key));
        return new Set([...current].filter((key) => valid.has(key)));
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load duplicate clips");
    }
  }, []);

  useEffect(() => {
    void loadDuplicates();
  }, [loadDuplicates]);

  const selectedClips = useMemo(
    () => duplicates.filter((clip) => selectedKeys.has(clip.key)),
    [duplicates, selectedKeys],
  );

  const selectedSegmentCount = useMemo(() => {
    const ids = new Set<number>();
    for (const clip of selectedClips) {
      for (const segmentId of clip.segment_ids) {
        ids.add(segmentId);
      }
    }
    return ids.size;
  }, [selectedClips]);

  const allSelected = duplicates.length > 0 && selectedKeys.size === duplicates.length;

  const toggleSelection = (key: string) => {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const selectAll = () => {
    setSelectedKeys(new Set(duplicates.map((clip) => clip.key)));
  };

  const clearSelection = () => {
    setSelectedKeys(new Set());
  };

  const fetchSegmentWithRetry = async (segmentId: number, provider: FetchProvider) => {
    // Backend treats unknown providers (including "commons") as mix.
    const apiProvider = provider === "commons" ? "mix" : provider;
    let lastError: unknown;
    for (let attempt = 1; attempt <= MAX_FETCH_ATTEMPTS; attempt += 1) {
      try {
        await apiFetch(
          `/api/fetch?segment_id=${segmentId}&refetch=true&provider=${apiProvider}`,
        );
        return;
      } catch (err) {
        lastError = err;
        if (attempt >= MAX_FETCH_ATTEMPTS) break;
        if (!isRetryableFetchError(err)) break;
        await sleep(retryDelayMs(attempt, err));
      }
    }
    throw lastError instanceof Error
      ? lastError
      : new Error(`Failed to refetch segment ${segmentId}`);
  };

  const refetchSegmentIds = async (
    segmentIds: number[],
    provider: FetchProvider,
    actionLabel: string,
  ) => {
    if (!segmentIds.length) {
      setStatus("Nothing to refetch — each selected batch only has one keepable segment.");
      return;
    }

    const failures: string[] = [];
    setProgress({
      label: actionLabel,
      done: 0,
      total: segmentIds.length,
      currentSegmentId: segmentIds[0] ?? null,
    });

    for (let index = 0; index < segmentIds.length; index += 1) {
      const segmentId = segmentIds[index];
      setProgress({
        label: actionLabel,
        done: index,
        total: segmentIds.length,
        currentSegmentId: segmentId,
      });
      try {
        await fetchSegmentWithRetry(segmentId, provider);
      } catch (err) {
        failures.push(
          `#${segmentId}: ${err instanceof Error ? err.message : "failed"}`,
        );
      }
      if (index < segmentIds.length - 1) {
        await sleep(REFETCH_DELAY_MS);
      }
    }

    setProgress({
      label: actionLabel,
      done: segmentIds.length,
      total: segmentIds.length,
      currentSegmentId: null,
    });

    await loadDuplicates();

    const ok = segmentIds.length - failures.length;
    setStatus(
      `${actionLabel}: ${ok}/${segmentIds.length} segment${segmentIds.length === 1 ? "" : "s"} updated` +
        (failures.length ? ` · ${failures.length} failed` : ""),
    );
    if (failures.length) {
      setError(failures.slice(0, 4).join(" · ") + (failures.length > 4 ? "…" : ""));
    }
  };

  const refetchSegments = async (
    clip: DuplicateClip,
    provider: FetchProvider,
    actionLabel: string,
  ) => {
    setBusyKey(clip.key);
    setStatus(null);
    setError(null);
    try {
      await refetchSegmentIds(segmentIdsToRefetch([clip]), provider, actionLabel);
    } catch (err) {
      setError(err instanceof Error ? err.message : `${actionLabel} failed`);
    } finally {
      setBusyKey(null);
      setProgress(null);
    }
  };

  const refetchSelected = async (provider: FetchProvider) => {
    if (!selectedClips.length) return;

    const segmentIds = segmentIdsToRefetch(selectedClips);
    setBulkBusy(true);
    setStatus(null);
    setError(null);
    try {
      const label =
        provider === "commons"
          ? `Refetch selected (${selectedClips.length} batch${selectedClips.length === 1 ? "" : "es"})`
          : `Refetch selected (${selectedClips.length} batch${selectedClips.length === 1 ? "" : "es"})`;
      await refetchSegmentIds(segmentIds, provider, label);
      setSelectedKeys(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk refetch failed");
    } finally {
      setBulkBusy(false);
      setProgress(null);
    }
  };

  const flagClip = async (clip: DuplicateClip) => {
    const segmentId = clip.segment_ids[0];
    if (segmentId == null) return;

    setBusyKey(clip.key);
    setStatus(null);
    setError(null);
    try {
      await apiFetch("/api/flagged", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segment_id: segmentId }),
      });
      await loadDuplicates();
      setStatus(`Flagged clip used in ${clip.count} segments`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to flag clip");
    } finally {
      setBusyKey(null);
    }
  };

  const flagSelected = async () => {
    if (!selectedClips.length) return;

    setBulkBusy(true);
    setStatus(null);
    setError(null);
    setProgress({
      label: "Flagging selected",
      done: 0,
      total: selectedClips.length,
      currentSegmentId: null,
    });
    try {
      for (let index = 0; index < selectedClips.length; index += 1) {
        const clip = selectedClips[index];
        const segmentId = clip.segment_ids[0];
        setProgress({
          label: "Flagging selected",
          done: index,
          total: selectedClips.length,
          currentSegmentId: segmentId ?? null,
        });
        if (segmentId == null) continue;
        await apiFetch("/api/flagged", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ segment_id: segmentId }),
        });
        await sleep(REFETCH_DELAY_MS);
      }
      setProgress({
        label: "Flagging selected",
        done: selectedClips.length,
        total: selectedClips.length,
        currentSegmentId: null,
      });
      await loadDuplicates();
      setStatus(`Flagged ${selectedClips.length} selected clip${selectedClips.length === 1 ? "" : "s"}`);
      setSelectedKeys(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk flag failed");
    } finally {
      setBulkBusy(false);
      setProgress(null);
    }
  };

  const anyBusy = bulkBusy || busyKey !== null;
  const progressPercent =
    progress && progress.total > 0
      ? Math.round((progress.done / progress.total) * 100)
      : 0;

  return (
    <main className="page-container w-full py-6 text-[var(--foreground)]">
      <div className="w-full">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Duplicate clips</h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Clips selected on more than one segment. Refetch keeps the first use and replaces the
              rest so reuse drops in the final video.
            </p>
            {summary.total_groups > 0 ? (
              <p className="glow-accent-text mt-1 text-sm text-[var(--accent)]">
                {summary.total_groups} duplicate clip{summary.total_groups === 1 ? "" : "s"} across{" "}
                {summary.total_segments_affected} segments
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void loadDuplicates()}
              disabled={anyBusy}
              className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
            >
              Refresh
            </button>
            <Link
              href="/"
              className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold"
            >
              Back to viewer
            </Link>
          </div>
        </div>

        {duplicates.length > 0 ? (
          <div className="glow-card mb-4 flex flex-wrap items-center gap-2 rounded-[14px] p-3">
            <label className="inline-flex items-center gap-2 text-sm text-[var(--muted)]">
              <Checkbox
                checked={allSelected}
                onCheckedChange={(checked) => {
                  if (checked) selectAll();
                  else clearSelection();
                }}
                disabled={anyBusy}
              />
              Select all
            </label>
            <span className="text-sm text-[var(--muted)]">
              {selectedKeys.size} batch{selectedKeys.size === 1 ? "" : "es"} selected
              {selectedKeys.size > 0 ? ` · ${selectedSegmentCount} segments` : ""}
            </span>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={anyBusy || selectedKeys.size === 0}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  void refetchSelected("mix");
                }}
                className="glow-btn-primary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
              >
                {bulkBusy ? "Working…" : "Refetch selected"}
              </button>
              <button
                type="button"
                disabled={anyBusy || selectedKeys.size === 0}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  void refetchSelected("commons");
                }}
                className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
              >
                Refetch selected (commons)
              </button>
              <button
                type="button"
                disabled={anyBusy || selectedKeys.size === 0}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  void flagSelected();
                }}
                className="glow-btn-flag rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
              >
                Flag selected
              </button>
            </div>
          </div>
        ) : null}

        {progress ? (
          <div className="glow-card mb-4 rounded-[14px] p-4">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-[var(--foreground)]">
                {progress.label}
                {progress.currentSegmentId != null ? ` · segment #${progress.currentSegmentId}` : ""}
              </span>
              <span className="tabular-nums text-[var(--muted)]">
                {progress.done}/{progress.total} · {progressPercent}%
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-raised)]">
              <div
                className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-200"
                style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
              />
            </div>
          </div>
        ) : null}

        {error ? <p className="mb-4 text-sm text-[#ffc9c9]">{error}</p> : null}
        {status ? <p className="mb-4 text-sm text-[#b9f3dc]">{status}</p> : null}

        {duplicates.length === 0 ? (
          <div className="glow-card rounded-[14px] p-8 text-center text-[var(--muted)]">
            No duplicate clips found — each selected clip is only used once.
          </div>
        ) : (
          <div className="grid gap-3">
            {duplicates.map((clip) => {
              const busy = busyKey === clip.key || bulkBusy;
              const selected = selectedKeys.has(clip.key);
              return (
                <article
                  key={clip.key}
                  role="button"
                  tabIndex={anyBusy ? -1 : 0}
                  onClick={() => {
                    if (anyBusy) return;
                    toggleSelection(clip.key);
                  }}
                  onKeyDown={(event) => {
                    if (anyBusy) return;
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      toggleSelection(clip.key);
                    }
                  }}
                  className={`glow-card flex flex-col gap-4 rounded-[14px] p-4 lg:flex-row lg:items-start ${
                    selected ? "glow-card-focused" : ""
                  } ${anyBusy ? "" : "cursor-pointer"}`}
                >
                  <div className="pointer-events-none flex shrink-0 items-start pt-1">
                    <Checkbox
                      checked={selected}
                      disabled={anyBusy}
                      aria-label={`Select duplicate batch ${clip.key}`}
                      tabIndex={-1}
                    />
                  </div>

                  <div className="glow-video-frame aspect-video w-full max-w-[220px] shrink-0 overflow-hidden rounded-[10px] bg-black">
                    {clip.thumbnail ? (
                      <img
                        src={clip.thumbnail}
                        alt=""
                        className="block h-full w-full object-cover"
                      />
                    ) : (
                      <div className="grid h-full place-items-center text-xs text-[var(--muted)]">
                        No thumbnail
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="glow-chip inline-flex px-2 py-0.5 text-[0.72rem] font-semibold">
                        Used {clip.count} times
                      </span>
                      <span className="text-sm text-[var(--muted)]">
                        {clip.provider || "unknown"}
                        {clip.video_id != null ? ` · #${clip.video_id}` : ""}
                      </span>
                    </div>
                    {clip.photographer ? (
                      <p className="mt-1 text-sm text-[var(--foreground)]">{clip.photographer}</p>
                    ) : null}
                    <p className="mt-2 text-sm text-[var(--muted)]">
                      Segments:{" "}
                      {clip.segment_ids.map((id, index) => (
                        <span key={id}>
                          {index > 0 ? ", " : ""}
                          <Link
                            href={`/?segment=${id}`}
                            className="text-[var(--foreground)] hover:underline"
                            onClick={(event) => event.stopPropagation()}
                          >
                            #{id}
                          </Link>
                        </span>
                      ))}
                    </p>
                    {clip.gaps && clip.gaps.length > 0 ? (
                      <p className="mt-1 text-sm text-[var(--muted)]">
                        Time gaps: {clip.gaps.map((gap) => formatGap(gap.gap_seconds)).join(" - ")}
                      </p>
                    ) : null}
                    {clip.pexels_url ? (
                      <a
                        href={clip.pexels_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(event) => event.stopPropagation()}
                        className="mt-2 inline-block text-[0.78rem] text-[var(--muted)] hover:text-[var(--foreground)]"
                      >
                        View on Pexels
                      </a>
                    ) : clip.pixabay_url ? (
                      <a
                        href={clip.pixabay_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(event) => event.stopPropagation()}
                        className="mt-2 inline-block text-[0.78rem] text-[var(--muted)] hover:text-[var(--foreground)]"
                      >
                        View on Pixabay
                      </a>
                    ) : null}
                  </div>

                  <div
                    className="flex shrink-0 flex-col gap-2 sm:flex-row lg:flex-col"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void refetchSegments(clip, "mix", "Refetched")}
                      className="glow-btn-primary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
                    >
                      {busyKey === clip.key ? "Working…" : "Refetch affected"}
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void refetchSegments(clip, "commons", "Refetched commons for")}
                      className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
                    >
                      Refetch commons
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void flagClip(clip)}
                      className="glow-btn-flag rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
                    >
                      Flag clip
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
