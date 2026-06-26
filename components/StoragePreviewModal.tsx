"use client";

import { useEffect, useMemo } from "react";
import { Download, X } from "lucide-react";
import { AudioPreviewPlayer } from "@/components/AudioPreviewPlayer";
import type { StorageItem } from "@/lib/r2";
import { AUDIO_PREVIEW_SECONDS, storageMediaUrl } from "@/lib/storage-media";

type StoragePreviewModalProps = {
  item: StorageItem | null;
  onClose: () => void;
};

export function StoragePreviewModal({ item, onClose }: StoragePreviewModalProps) {
  const previewUrl = useMemo(
    () => (item ? storageMediaUrl(item.key) : ""),
    [item],
  );
  const downloadUrl = useMemo(
    () => (item ? storageMediaUrl(item.key, true) : ""),
    [item],
  );

  useEffect(() => {
    if (!item) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [item, onClose]);

  if (!item) return null;

  const isVideo = item.type === "video";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      onClick={onClose}
    >
      <div
        className="glow-card flex w-full max-w-3xl flex-col overflow-hidden rounded-[var(--radius-lg)]"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="preview-modal-title"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
          <div className="min-w-0">
            <h2 id="preview-modal-title" className="truncate text-lg font-semibold">
              {item.name}
            </h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {isVideo ? "Video preview" : `Audio preview · first ${AUDIO_PREVIEW_SECONDS}s only`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="glow-btn-secondary shrink-0 rounded-[var(--radius-sm)] p-2"
            aria-label="Close preview"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="bg-black px-5 py-5">
          {isVideo ? (
            <video
              key={previewUrl}
              src={previewUrl}
              controls
              autoPlay
              playsInline
              className="max-h-[60vh] w-full rounded-[var(--radius)] bg-black"
            />
          ) : (
            <AudioPreviewPlayer key={previewUrl} src={previewUrl} label={item.name} />
          )}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[var(--border)] px-5 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="glow-btn-secondary px-4 py-2.5 text-sm font-semibold"
          >
            Close
          </button>
          <a
            href={downloadUrl}
            download={item.name}
            className="glow-btn-primary inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold"
          >
            <Download className="h-4 w-4" />
            Download full file
          </a>
        </div>
      </div>
    </div>
  );
}
