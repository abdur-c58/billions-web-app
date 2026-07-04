"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Folder, FolderPlus, Loader2, X } from "lucide-react";
import { ExportStyleProgressBar } from "@/components/ExportStyleProgressBar";
import type { StorageItem } from "@/lib/r2";
import { fetchYoutubeAudioJob, startYoutubeAudioDownload } from "@/lib/youtube-audio";
import { cn } from "@/lib/utils";
import { STATUS_POLL_MS } from "@/hooks/usePolling";

type ListResponse = {
  prefix: string;
  items: StorageItem[];
};

type DownloadYtAudioModalProps = {
  open: boolean;
  initialPrefix?: string;
  onClose: () => void;
  onComplete: (result: { key: string; name: string; title: string }) => void;
  onJobStarted?: (jobId: string) => void;
};

const AUDIO_PREFIX = "Audio/";

function looksLikeYoutubeUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (/^[\w-]{11}$/.test(trimmed)) return true;
  return /youtube\.com|youtu\.be/.test(trimmed);
}

export function DownloadYtAudioModal({
  open,
  initialPrefix = AUDIO_PREFIX,
  onClose,
  onComplete,
  onJobStarted,
}: DownloadYtAudioModalProps) {
  const [step, setStep] = useState<"url" | "folder">("url");
  const [url, setUrl] = useState("");
  const [prefix, setPrefix] = useState(AUDIO_PREFIX);
  const [items, setItems] = useState<StorageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobMessage, setJobMessage] = useState("Starting download…");

  const breadcrumbs = useMemo(() => {
    if (!prefix) return [];
    return prefix.replace(/\/$/, "").split("/");
  }, [prefix]);

  const resetState = useCallback(() => {
    setStep("url");
    setUrl("");
    setPrefix(AUDIO_PREFIX);
    setItems([]);
    setLoading(false);
    setDownloading(false);
    setCreatingFolder(false);
    setFolderName("");
    setError(null);
    setActiveJobId(null);
    setJobProgress(0);
    setJobMessage("Starting download…");
  }, []);

  const loadPrefix = useCallback(async (nextPrefix: string) => {
    const normalized = nextPrefix.startsWith(AUDIO_PREFIX) ? nextPrefix : AUDIO_PREFIX;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/storage?prefix=${encodeURIComponent(normalized)}`);
      const payload = (await response.json()) as ListResponse & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Failed to load folders");
      if (!payload.prefix.startsWith(AUDIO_PREFIX)) {
        throw new Error("Destination must stay inside the Audio folder.");
      }
      setPrefix(payload.prefix);
      setItems(payload.items.filter((entry) => entry.type === "folder"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load folders");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    resetState();
    const startPrefix = initialPrefix.startsWith(AUDIO_PREFIX) ? initialPrefix : AUDIO_PREFIX;
    setPrefix(startPrefix);
  }, [open, initialPrefix, resetState]);

  useEffect(() => {
    if (!open || step !== "folder") return;
    void loadPrefix(prefix.startsWith(AUDIO_PREFIX) ? prefix : AUDIO_PREFIX);
  }, [open, step, loadPrefix, prefix]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !downloading) onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, downloading, onClose]);

  useEffect(() => {
    if (!activeJobId || !downloading) return;

    let cancelled = false;
    let timer: number | null = null;

    const poll = async () => {
      try {
        const job = await fetchYoutubeAudioJob(activeJobId);
        if (cancelled) return;

        setJobProgress(job.progress_percent ?? 0);
        setJobMessage(job.message || "Downloading…");

        if (job.status === "done" && job.key && job.name) {
          onComplete({
            key: job.key,
            name: job.name,
            title: job.title || job.name,
          });
          setDownloading(false);
          setActiveJobId(null);
          onClose();
          return;
        }

        if (job.status === "error") {
          setError(job.error || job.message || "Download failed");
          setDownloading(false);
          setActiveJobId(null);
          return;
        }

        timer = window.setTimeout(poll, STATUS_POLL_MS);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to read download progress");
        setDownloading(false);
        setActiveJobId(null);
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [activeJobId, downloading, onClose, onComplete]);

  if (!open) return null;

  const urlValid = looksLikeYoutubeUrl(url);
  const canDownload = prefix.startsWith(AUDIO_PREFIX) && !downloading && !loading;

  const openFolder = (item: StorageItem) => {
    if (item.type !== "folder") return;
    void loadPrefix(item.key);
  };

  const goToCrumb = (index: number) => {
    const parts = breadcrumbs.slice(0, index + 1);
    void loadPrefix(parts.length ? `${parts.join("/")}/` : AUDIO_PREFIX);
  };

  const handleNext = () => {
    if (!urlValid) {
      setError("Paste a valid YouTube link or video ID.");
      return;
    }
    setError(null);
    setStep("folder");
  };

  const createFolder = async () => {
    const name = folderName.trim();
    if (!name) return;
    setCreatingFolder(true);
    setError(null);
    try {
      const response = await fetch("/api/storage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prefix, folderName: name }),
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(payload.error || "Failed to create folder");
      setFolderName("");
      await loadPrefix(prefix);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create folder");
    } finally {
      setCreatingFolder(false);
    }
  };

  const handleDownload = async () => {
    if (!canDownload) return;
    setDownloading(true);
    setError(null);
    setJobProgress(0);
    setJobMessage("Starting download…");
    try {
      const payload = await startYoutubeAudioDownload(url.trim(), prefix);
      setActiveJobId(payload.job_id);
      onJobStarted?.(payload.job_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Download failed";
      if (/not available on the running backend|npm run dev:api|ytserver/i.test(message)) {
        setError(message);
      } else if (/not found/i.test(message)) {
        setError(
          "YouTube audio download is not available on the running backend. Restart it: npm run dev:api (or ytserver).",
        );
      } else {
        setError(message);
      }
      setDownloading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-4"
      onClick={() => {
        onClose();
      }}
    >
      <div
        className="glow-card flex max-h-[85vh] w-full max-w-lg flex-col rounded-[var(--radius-lg)] p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="download-yt-audio-title"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="download-yt-audio-title" className="text-lg font-semibold">
              Download YouTube audio
            </h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {step === "url"
                ? "Step 1 of 2 — paste a YouTube link"
                : "Step 2 of 2 — choose a folder in Audio"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="glow-btn-secondary rounded-[var(--radius-sm)] p-2"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {step === "url" ? (
          <>
            <label className="mb-4 block">
              <span className="mb-1 block text-sm text-[var(--muted)]">YouTube URL</span>
              <input
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=…"
                className="glow-control w-full px-3 py-2.5"
                autoFocus
              />
            </label>
          </>
        ) : (
          <>
            <div className="mb-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={loading || downloading}
                className="glow-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:opacity-55"
                onClick={() => void loadPrefix(AUDIO_PREFIX)}
              >
                Audio
              </button>
              {breadcrumbs.slice(1).map((crumb, index) => (
                <button
                  key={`${crumb}-${index + 1}`}
                  type="button"
                  disabled={loading || downloading}
                  className="glow-btn-secondary px-3 py-1.5 text-xs font-semibold disabled:opacity-55"
                  onClick={() => goToCrumb(index + 1)}
                >
                  {crumb}
                </button>
              ))}
            </div>

            <div className="mb-3 flex flex-wrap items-end gap-2">
              <label className="min-w-[140px] flex-1">
                <span className="mb-1 block text-xs text-[var(--muted)]">New subfolder</span>
                <input
                  value={folderName}
                  onChange={(event) => setFolderName(event.target.value)}
                  placeholder="Folder name"
                  disabled={downloading}
                  className="glow-control w-full px-3 py-2"
                />
              </label>
              <button
                type="button"
                disabled={downloading || creatingFolder || !folderName.trim()}
                onClick={() => void createFolder()}
                className="glow-btn-secondary inline-flex items-center gap-1.5 px-3 py-2 text-sm font-semibold disabled:opacity-55"
              >
                {creatingFolder ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FolderPlus className="h-4 w-4" />
                )}
                Create
              </button>
            </div>

            <div className="mb-3 min-h-[200px] flex-1 overflow-y-auto rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-raised)]">
              {loading ? (
                <div className="flex items-center gap-2 p-4 text-sm text-[var(--muted)]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading folders…
                </div>
              ) : items.length === 0 ? (
                <p className="p-4 text-sm text-[var(--muted)]">
                  No subfolders here. Save to this folder or create one above.
                </p>
              ) : (
                <ul>
                  {items.map((item) => (
                    <li key={item.key}>
                      <button
                        type="button"
                        disabled={downloading}
                        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm hover:bg-[var(--card)] disabled:opacity-55"
                        onClick={() => openFolder(item)}
                      >
                        <Folder className="h-4 w-4 text-[var(--muted)]" />
                        {item.name}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="mb-3 text-xs text-[var(--muted)]">
              Save to: {breadcrumbs.join(" / ") || "Audio"}
            </p>
          </>
        )}

        {error ? <p className="mb-3 text-sm text-red-300">{error}</p> : null}

        {downloading ? (
          <div className="mb-4 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)] p-4">
            <div className="mb-3 flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">Downloading YouTube audio</span>
              <span className="tabular-nums text-[var(--muted)]">{jobProgress}%</span>
            </div>
            <ExportStyleProgressBar percent={jobProgress} />
            <p className="mt-3 text-xs text-[var(--muted)]">{jobMessage}</p>
          </div>
        ) : null}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {step === "folder" ? (
            <button
              type="button"
              disabled={downloading}
              onClick={() => {
                setError(null);
                setStep("url");
              }}
              className="glow-btn-secondary px-4 py-2.5 text-sm font-semibold disabled:opacity-55"
            >
              Back
            </button>
          ) : (
            <button
              type="button"
              onClick={onClose}
              className="glow-btn-secondary px-4 py-2.5 text-sm font-semibold"
            >
              Cancel
            </button>
          )}
          {step === "url" ? (
            <button
              type="button"
              disabled={!urlValid}
              onClick={handleNext}
              className={cn(
                "glow-btn-primary px-4 py-2.5 text-sm font-semibold disabled:opacity-55",
              )}
            >
              Next
            </button>
          ) : (
            <button
              type="button"
              disabled={!canDownload}
              onClick={() => void handleDownload()}
              className={cn(
                "glow-btn-primary inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold disabled:opacity-55",
              )}
            >
              {downloading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Downloading…
                </>
              ) : (
                "Download"
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
