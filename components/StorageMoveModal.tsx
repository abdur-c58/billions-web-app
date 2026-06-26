"use client";

import { useCallback, useEffect, useState } from "react";
import { Folder, Loader2, X } from "lucide-react";
import type { StorageItem } from "@/lib/r2";
import { cn } from "@/lib/utils";

type ListResponse = {
  prefix: string;
  items: StorageItem[];
};

type StorageMoveModalProps = {
  item: StorageItem | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: (item: StorageItem, destinationPrefix: string) => void;
};

export function StorageMoveModal({
  item,
  busy,
  onClose,
  onConfirm,
}: StorageMoveModalProps) {
  const [browsePrefix, setBrowsePrefix] = useState("");
  const [folders, setFolders] = useState<StorageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const breadcrumbs = browsePrefix
    ? browsePrefix.replace(/\/$/, "").split("/")
    : [];

  const loadFolders = useCallback(async (prefix: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/storage?prefix=${encodeURIComponent(prefix)}`);
      const payload = (await response.json()) as ListResponse & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Failed to load folders");
      setBrowsePrefix(payload.prefix);
      setFolders(payload.items.filter((entry) => entry.type === "folder"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load folders");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!item) return;
    void loadFolders("");
  }, [item, loadFolders]);

  if (!item) return null;

  const isFolder = item.type === "folder";
  const invalidDestinations = new Set<string>([
    item.key,
    ...(isFolder ? [item.key] : []),
  ]);

  const canMoveHere =
    browsePrefix !== "" &&
    !invalidDestinations.has(browsePrefix) &&
    !(isFolder && browsePrefix.startsWith(item.key));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="glow-card flex max-h-[85vh] w-full max-w-lg flex-col rounded-[var(--radius-lg)] p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-modal-title"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="move-modal-title" className="text-lg font-semibold">
              Move {isFolder ? "folder" : "file"}
            </h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              <span className="font-medium text-[var(--foreground)]">{item.name}</span>
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

        <p className="mb-3 text-sm text-[var(--muted)]">Choose a destination folder:</p>

        <div className="mb-3 flex flex-wrap gap-2">
          <button
            type="button"
            className="glow-btn-secondary px-3 py-1.5 text-xs font-semibold"
            onClick={() => void loadFolders("")}
          >
            Root
          </button>
          {breadcrumbs.map((crumb, index) => (
            <button
              key={`${crumb}-${index}`}
              type="button"
              className="glow-btn-secondary px-3 py-1.5 text-xs font-semibold"
              onClick={() => {
                const parts = breadcrumbs.slice(0, index + 1);
                void loadFolders(parts.length ? `${parts.join("/")}/` : "");
              }}
            >
              {crumb}
            </button>
          ))}
        </div>

        <div className="mb-4 min-h-[200px] flex-1 overflow-y-auto rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-raised)]">
          {loading ? (
            <div className="flex items-center gap-2 p-4 text-sm text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading folders…
            </div>
          ) : browsePrefix === "" ? (
            <ul>
              {folders.map((folder) => (
                <li key={folder.key}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm hover:bg-[var(--card)]"
                    onClick={() => void loadFolders(folder.key)}
                  >
                    <Folder className="h-4 w-4 text-[var(--muted)]" />
                    {folder.name}
                  </button>
                </li>
              ))}
            </ul>
          ) : folders.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted)]">No subfolders here.</p>
          ) : (
            <ul>
              {folders
                .filter(
                  (folder) =>
                    !invalidDestinations.has(folder.key) &&
                    !(isFolder && folder.key.startsWith(item.key)),
                )
                .map((folder) => (
                  <li key={folder.key}>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm hover:bg-[var(--card)]"
                      onClick={() => void loadFolders(folder.key)}
                    >
                      <Folder className="h-4 w-4 text-[var(--muted)]" />
                      {folder.name}
                    </button>
                  </li>
                ))}
            </ul>
          )}
        </div>

        {error ? (
          <p className="mb-3 text-sm text-red-300">{error}</p>
        ) : null}

        <p className="mb-4 text-xs text-[var(--muted)]">
          {browsePrefix
            ? `Destination: ${breadcrumbs.join(" / ")}`
            : "Open a root folder (Audio, B-Roll, or Other) to select a destination."}
        </p>

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="glow-btn-secondary px-4 py-2.5 text-sm font-semibold disabled:opacity-55"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy || !canMoveHere}
            onClick={() => onConfirm(item, browsePrefix)}
            className={cn(
              "glow-btn-primary px-4 py-2.5 text-sm font-semibold disabled:opacity-55",
            )}
          >
            {busy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Moving…
              </>
            ) : (
              "Move here"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
