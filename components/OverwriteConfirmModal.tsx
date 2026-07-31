"use client";

import { Loader2 } from "lucide-react";

export type OverwriteConflict = {
  title: string;
  projectName: string;
  fileName: string;
};

type OverwriteConfirmModalProps = {
  conflicts: OverwriteConflict[];
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function OverwriteConfirmModal({
  conflicts,
  busy = false,
  onConfirm,
  onCancel,
}: OverwriteConfirmModalProps) {
  const count = conflicts.length;
  const label = count === 1 ? "1 existing project" : `${count} existing projects`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(4,8,18,0.72)] p-4 backdrop-blur-[2px]">
      <div
        className="glow-card w-full max-w-lg p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="overwrite-confirm-title"
      >
        <h3 id="overwrite-confirm-title" className="text-xl font-semibold">
          Overwrite existing project{count === 1 ? "" : "s"}?
        </h3>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          {label} already use the same video title. Overwriting deletes those projects and any
          matching exports under Documents/ExportedVids.
        </p>

        <ul className="mt-4 max-h-48 space-y-2 overflow-y-auto text-sm">
          {conflicts.map((conflict) => (
            <li
              key={`${conflict.fileName}-${conflict.title}`}
              className="rounded-[8px] border border-[var(--border)] px-3 py-2"
            >
              <p className="font-medium text-[var(--foreground)]">{conflict.title}</p>
              <p className="text-[var(--muted)]">
                Existing: {conflict.projectName} · from {conflict.fileName}
              </p>
            </li>
          ))}
        </ul>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className="glow-btn-primary flex-1 px-4 py-3 text-sm font-semibold disabled:opacity-55"
          >
            {busy ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Overwrite"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="flex-1 rounded-[var(--radius-lg)] border border-[var(--border)] px-4 py-3 text-sm font-semibold text-[var(--muted)] transition-colors hover:text-[var(--foreground)] disabled:opacity-55"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
