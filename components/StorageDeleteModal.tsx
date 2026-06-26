"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, X } from "lucide-react";
import type { StorageItem } from "@/lib/r2";

const HOLD_MS = 1000;

type StorageDeleteModalProps = {
  item: StorageItem | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: (item: StorageItem) => void;
};

export function StorageDeleteModal({
  item,
  busy,
  onClose,
  onConfirm,
}: StorageDeleteModalProps) {
  const [holdProgress, setHoldProgress] = useState(0);
  const holdingRef = useRef(false);
  const frameRef = useRef<number | null>(null);
  const startRef = useRef(0);

  const cancelHold = useCallback(() => {
    holdingRef.current = false;
    startRef.current = 0;
    setHoldProgress(0);
    if (frameRef.current != null) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!item) cancelHold();
  }, [item, cancelHold]);

  useEffect(() => {
    return () => cancelHold();
  }, [cancelHold]);

  const tick = useCallback(() => {
    if (!holdingRef.current) return;
    const elapsed = Date.now() - startRef.current;
    const progress = Math.min(100, (elapsed / HOLD_MS) * 100);
    setHoldProgress(progress);
    if (progress >= 100) {
      holdingRef.current = false;
      if (item) onConfirm(item);
      cancelHold();
      return;
    }
    frameRef.current = requestAnimationFrame(tick);
  }, [cancelHold, item, onConfirm]);

  const startHold = () => {
    if (busy || !item) return;
    holdingRef.current = true;
    startRef.current = Date.now();
    frameRef.current = requestAnimationFrame(tick);
  };

  if (!item) return null;

  const isFolder = item.type === "folder";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="glow-card w-full max-w-md rounded-[var(--radius-lg)] p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-modal-title"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="delete-modal-title" className="text-lg font-semibold">
              Delete {isFolder ? "folder" : "file"}?
            </h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              <span className="font-medium text-[var(--foreground)]">{item.name}</span> will be
              permanently removed from storage.
              {isFolder ? " Only the folder marker is deleted if it still has contents." : ""}
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
            disabled={busy}
            onPointerDown={(event) => {
              event.preventDefault();
              startHold();
            }}
            onPointerUp={cancelHold}
            onPointerLeave={cancelHold}
            onPointerCancel={cancelHold}
            className="hold-delete-btn relative min-w-[180px] overflow-hidden rounded-[var(--radius)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-55"
          >
            <span
              className="hold-delete-btn-fill"
              style={{ width: `${holdProgress}%` }}
              aria-hidden="true"
            />
            <span className="relative z-10 inline-flex items-center justify-center gap-2">
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Deleting…
                </>
              ) : holdProgress > 0 ? (
                "Keep holding…"
              ) : (
                "Hold 1s to delete"
              )}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
