"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, FileJson, Loader2, Music, Play } from "lucide-react";
import type { StorageItem } from "@/lib/r2";
import type { ProjectStorageItem } from "@/lib/project-r2";
import { storageMediaUrl } from "@/lib/storage-media";

type ProjectFilesResponse = {
  items: ProjectStorageItem[];
  ttlDays: number;
  configured?: boolean;
  error?: string;
};

function formatSize(size: number | null) {
  if (size == null) return "—";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatExpiry(iso: string) {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

type StorageProjectFilesProps = {
  onPreview: (item: StorageItem) => void;
};

export function StorageProjectFiles({ onPreview }: StorageProjectFilesProps) {
  const [items, setItems] = useState<ProjectStorageItem[]>([]);
  const [ttlDays, setTtlDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/storage/project");
      const payload = (await response.json()) as ProjectFilesResponse;
      if (!response.ok) throw new Error(payload.error || "Failed to load project files");
      if (payload.configured === false) {
        throw new Error("R2 is not configured for project file storage.");
      }
      setItems(payload.items);
      setTtlDays(payload.ttlDays);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project files");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const toPreviewItem = (file: ProjectStorageItem): StorageItem => ({
    key: file.key,
    name: file.name,
    type: file.name.endsWith(".mp3") ? "audio" : "other",
    size: file.size,
    lastModified: file.lastModified,
  });

  return (
    <div className="space-y-4">
      <div className="glow-card rounded-[var(--radius-lg)] border border-[var(--border)] px-4 py-3 text-sm text-[var(--muted)]">
        Active project files from the b-roll pipeline. They are stored privately in R2 and
        automatically deleted after {ttlDays} days without updates.
      </div>

      {error ? (
        <p className="rounded-[var(--radius)] border border-red-500/35 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-[var(--muted)]">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading project files…
        </div>
      ) : items.length === 0 ? (
        <div className="glow-card px-4 py-16 text-center text-[var(--muted)]">
          No project files in R2 yet. Import script, audio, and timestamps from the viewer setup
          page.
        </div>
      ) : (
        <div className="glow-card overflow-hidden rounded-[var(--radius-lg)]">
          <ul>
            {items.map((file) => {
              const isAudio = file.name.endsWith(".mp3");
              return (
                <li
                  key={file.key}
                  className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3 last:border-b-0"
                >
                  {isAudio ? (
                    <Music className="h-4 w-4 shrink-0 text-[var(--muted)]" />
                  ) : (
                    <FileJson className="h-4 w-4 shrink-0 text-[var(--muted)]" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{file.name}</p>
                    <p className="text-xs text-[var(--muted)]">
                      {file.projectId ? `${file.projectId} · ` : ""}
                      Expires {formatExpiry(file.expiresAt)} · {formatSize(file.size)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    {isAudio ? (
                      <button
                        type="button"
                        onClick={() => onPreview(toPreviewItem(file))}
                        className="glow-btn-secondary rounded-[var(--radius-sm)] p-2"
                        aria-label={`Preview ${file.name}`}
                        title="Preview"
                      >
                        <Play className="h-4 w-4" />
                      </button>
                    ) : null}
                    <a
                      href={storageMediaUrl(file.key, true)}
                      download={file.name}
                      className="glow-btn-secondary rounded-[var(--radius-sm)] p-2"
                      aria-label={`Download ${file.name}`}
                      title="Download"
                    >
                      <Download className="h-4 w-4" />
                    </a>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
