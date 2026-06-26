"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Folder, Loader2, Music2, X } from "lucide-react";
import type { StorageItem } from "@/lib/r2";
import { cn } from "@/lib/utils";

type ListResponse = {
  prefix: string;
  items: StorageItem[];
};

export type StorageAudioPick = {
  key: string;
  name: string;
  size_bytes: number | null;
};

type StorageAudioPickModalProps = {
  open: boolean;
  onClose: () => void;
  onSelect: (pick: StorageAudioPick) => void;
};

const DEFAULT_PREFIX = "Audio/";

function formatBytes(bytes: number | null) {
  if (bytes == null) return "";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function StorageAudioPickModal({ open, onClose, onSelect }: StorageAudioPickModalProps) {
  const [prefix, setPrefix] = useState(DEFAULT_PREFIX);
  const [items, setItems] = useState<StorageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        payload.items.filter((entry) => entry.type === "folder" || entry.type === "audio"),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load storage");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) {
      setError(null);
      return;
    }
    setPrefix(DEFAULT_PREFIX);
    void loadPrefix(DEFAULT_PREFIX);
  }, [loadPrefix, open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const openFolder = (item: StorageItem) => {
    if (item.type !== "folder") return;
    void loadPrefix(item.key);
  };

  const goToCrumb = (index: number) => {
    const parts = breadcrumbs.slice(0, index + 1);
    void loadPrefix(parts.length ? `${parts.join("/")}/` : "");
  };

  const handleChooseFile = (item: StorageItem) => {
    if (item.type !== "audio") return;
    onSelect({
      key: item.key,
      name: item.name,
      size_bytes: item.size,
    });
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-4"
      onClick={onClose}
    >
      <div
        className="glow-card flex max-h-[80vh] w-full max-w-lg flex-col rounded-[var(--radius-lg)]"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="storage-audio-pick-title"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
          <div className="min-w-0">
            <h2 id="storage-audio-pick-title" className="text-base font-semibold">
              Choose background audio
            </h2>
            <p className="mt-0.5 text-xs text-[var(--muted)]">Browse files in Storage → Audio</p>
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

        <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--border)] px-4 py-2">
          <button
            type="button"
            disabled={loading}
            onClick={() => void loadPrefix(DEFAULT_PREFIX)}
            className="glow-btn-secondary px-2.5 py-1 text-xs font-semibold disabled:opacity-55"
          >
            Audio
          </button>
          {breadcrumbs.slice(1).map((crumb, index) => (
            <button
              key={`crumb-${index + 1}-${crumb || "segment"}`}
              type="button"
              disabled={loading}
              onClick={() => goToCrumb(index + 1)}
              className="glow-btn-secondary px-2.5 py-1 text-xs font-semibold disabled:opacity-55"
            >
              {crumb}
            </button>
          ))}
        </div>

        <div className="min-h-[240px] flex-1 overflow-y-auto px-1 py-1">
          {loading ? (
            <div className="flex items-center gap-2 px-3 py-6 text-sm text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading…
            </div>
          ) : items.length === 0 ? (
            <p className="px-3 py-6 text-sm text-[var(--muted)]">
              No audio files here. Upload MP3s to the Audio folder in Storage.
            </p>
          ) : (
            <ul>
              {items.map((item, index) => {
                const isFolder = item.type === "folder";
                const Icon = isFolder ? Folder : Music2;
                const rowKey = item.key || `${prefix}item-${index}`;
                return (
                  <li key={rowKey}>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => (isFolder ? openFolder(item) : handleChooseFile(item))}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-[var(--radius)] px-3 py-2.5 text-left text-sm transition-colors hover:bg-[var(--surface-raised)] disabled:opacity-55",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0 text-[var(--muted)]" />
                      <span className="min-w-0 flex-1 truncate font-medium">{item.name}</span>
                      <span className="shrink-0 text-xs text-[var(--muted)]">
                        {isFolder ? "Folder" : formatBytes(item.size)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {error ? <p className="px-4 pb-3 text-sm text-red-300">{error}</p> : null}
      </div>
    </div>
  );
}
