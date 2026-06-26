"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Film, Folder, HardDrive, Loader2, X } from "lucide-react";
import type { StorageItem } from "@/lib/r2";
import type { ViewerSegment } from "@/lib/types";
import { probeVideoDuration, storageMediaUrl } from "@/lib/storage-media";
import { cn } from "@/lib/utils";

type ListResponse = {
  prefix: string;
  items: StorageItem[];
};

type PendingClip = {
  item: StorageItem;
  duration: number | null;
};

type StorageClipSelectModalProps = {
  segment: ViewerSegment | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: (payload: {
    storageKey: string;
    name: string;
    duration: number | null;
    loop: boolean;
  }) => void;
};

const DEFAULT_PREFIX = "B-Roll/";

function formatSeconds(seconds: number) {
  return `${seconds.toFixed(1)}s`;
}

export function StorageClipSelectModal({
  segment,
  busy,
  onClose,
  onConfirm,
}: StorageClipSelectModalProps) {
  const [prefix, setPrefix] = useState(DEFAULT_PREFIX);
  const [items, setItems] = useState<StorageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingClip | null>(null);

  const segmentDuration = segment?.timing.duration_seconds ?? null;

  const breadcrumbs = useMemo(() => {
    if (!prefix) return [];
    return prefix.replace(/\/$/, "").split("/");
  }, [prefix]);

  const loadPrefix = useCallback(async (nextPrefix: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/storage?prefix=${encodeURIComponent(nextPrefix)}`);
      const payload = (await response.json()) as ListResponse & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Failed to load storage");
      setPrefix(payload.prefix);
      setItems(
        payload.items.filter(
          (entry) => entry.type === "folder" || entry.type === "video",
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load storage");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!segment) {
      setPending(null);
      setError(null);
      return;
    }
    setPrefix(DEFAULT_PREFIX);
    setPending(null);
    void loadPrefix(DEFAULT_PREFIX);
  }, [segment, loadPrefix]);

  useEffect(() => {
    if (!segment) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy && !probing) onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [segment, busy, probing, onClose]);

  if (!segment) return null;

  const openFolder = (item: StorageItem) => {
    if (item.type !== "folder") return;
    void loadPrefix(item.key);
  };

  const goToCrumb = (index: number) => {
    const parts = breadcrumbs.slice(0, index + 1);
    void loadPrefix(parts.length ? `${parts.join("/")}/` : "");
  };

  const handleChooseFile = async (item: StorageItem) => {
    if (item.type !== "video") return;
    setProbing(true);
    setError(null);
    try {
      const duration = await probeVideoDuration(storageMediaUrl(item.key));
      const needsWarning =
        segmentDuration != null &&
        segmentDuration > 0 &&
        duration != null &&
        duration + 0.05 < segmentDuration;

      if (needsWarning) {
        setPending({ item, duration });
        return;
      }

      onConfirm({
        storageKey: item.key,
        name: item.name,
        duration,
        loop: false,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to inspect clip");
    } finally {
      setProbing(false);
    }
  };

  const shortfall =
    pending && segmentDuration != null && pending.duration != null
      ? segmentDuration - pending.duration
      : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      onClick={() => {
        if (!busy && !probing) onClose();
      }}
    >
      <div
        className="glow-card flex max-h-[88vh] w-full max-w-2xl flex-col rounded-[var(--radius-lg)]"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="storage-clip-title"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
          <div className="min-w-0">
            <h2 id="storage-clip-title" className="text-lg font-semibold">
              Choose clip from storage
            </h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Segment {segment.segment_id}
              {segmentDuration != null ? ` · needs ${formatSeconds(segmentDuration)}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy || probing}
            className="glow-btn-secondary rounded-[var(--radius-sm)] p-2 disabled:opacity-55"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {pending ? (
          <div className="space-y-4 px-5 py-5">
            <div className="rounded-[var(--radius)] border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              <p className="font-medium">Clip is shorter than this segment</p>
              <p className="mt-2 text-[var(--muted)]">
                <span className="text-[var(--foreground)]">{pending.item.name}</span> is{" "}
                {pending.duration != null ? formatSeconds(pending.duration) : "unknown"} long, but
                segment {segment.segment_id} needs{" "}
                {segmentDuration != null ? formatSeconds(segmentDuration) : "more time"}.
                {shortfall != null && shortfall > 0
                  ? ` That is ${formatSeconds(shortfall)} short.`
                  : ""}
              </p>
              <p className="mt-2 text-[var(--muted)]">
                You can pick a longer clip, cancel, or use this clip and loop it until the segment
                ends during export.
              </p>
            </div>

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                disabled={busy}
                onClick={onClose}
                className="glow-btn-secondary px-4 py-2.5 text-sm font-semibold disabled:opacity-55"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setPending(null)}
                className="glow-btn-secondary px-4 py-2.5 text-sm font-semibold disabled:opacity-55"
              >
                Choose another clip
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  onConfirm({
                    storageKey: pending.item.key,
                    name: pending.item.name,
                    duration: pending.duration,
                    loop: true,
                  })
                }
                className="glow-btn-primary px-4 py-2.5 text-sm font-semibold disabled:opacity-55"
              >
                {busy ? "Saving…" : "Use clip and loop"}
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)] px-5 py-3">
              <button
                type="button"
                disabled={loading || probing}
                onClick={() => void loadPrefix("")}
                className="glow-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:opacity-55"
              >
                Root
              </button>
              {breadcrumbs.map((crumb, index) => (
                <button
                  key={`${crumb}-${index}`}
                  type="button"
                  disabled={loading || probing}
                  onClick={() => goToCrumb(index)}
                  className="glow-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:opacity-55"
                >
                  {crumb}
                </button>
              ))}
            </div>

            <div className="min-h-[280px] flex-1 overflow-y-auto px-2 py-2">
              {loading ? (
                <div className="flex items-center gap-2 px-3 py-6 text-sm text-[var(--muted)]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading storage…
                </div>
              ) : items.length === 0 ? (
                <p className="px-3 py-6 text-sm text-[var(--muted)]">
                  No video files here. Open B-Roll or upload footage first.
                </p>
              ) : (
                <ul>
                  {items.map((item) => {
                    const isFolder = item.type === "folder";
                    const Icon = isFolder ? Folder : Film;
                    return (
                      <li key={item.key}>
                        <button
                          type="button"
                          disabled={probing || busy}
                          onClick={() =>
                            isFolder ? openFolder(item) : void handleChooseFile(item)
                          }
                          className={cn(
                            "flex w-full items-center gap-3 rounded-[var(--radius)] px-3 py-3 text-left text-sm transition-colors hover:bg-[var(--surface-raised)] disabled:opacity-55",
                          )}
                        >
                          <Icon className="h-4 w-4 shrink-0 text-[var(--muted)]" />
                          <span className="min-w-0 flex-1 truncate font-medium">{item.name}</span>
                          <span className="text-xs text-[var(--muted)]">
                            {isFolder ? "Folder" : "Video"}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {error ? (
              <p className="px-5 pb-2 text-sm text-red-300">{error}</p>
            ) : null}

            {probing ? (
              <div className="flex items-center gap-2 border-t border-[var(--border)] px-5 py-3 text-sm text-[var(--muted)]">
                <Loader2 className="h-4 w-4 animate-spin" />
                Checking clip duration…
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
