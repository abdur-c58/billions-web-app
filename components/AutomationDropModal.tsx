"use client";

import { Loader2 } from "lucide-react";
import type { AutomationGoal } from "@/lib/automation";

type AutomationDropModalProps = {
  fileCount: number;
  busy?: boolean;
  onChoose: (goal: AutomationGoal) => void;
  onCancel: () => void;
};

export function AutomationDropModal({
  fileCount,
  busy = false,
  onChoose,
  onCancel,
}: AutomationDropModalProps) {
  const label = fileCount === 1 ? "1 script" : `${fileCount} scripts`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(4,8,18,0.72)] p-4 backdrop-blur-[2px]">
      <div
        className="glow-card w-full max-w-lg p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="automation-drop-title"
      >
        <h3 id="automation-drop-title" className="text-xl font-semibold">
          How should automation run?
        </h3>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          You dropped {label}. Choose what happens after import.
        </p>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            disabled={busy}
            onClick={() => onChoose("fetch_review")}
            className="glow-btn-primary flex-1 px-4 py-3 text-sm font-semibold disabled:opacity-55"
          >
            {busy ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Fetch & review"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onChoose("auto_export")}
            className="flex-1 rounded-[var(--radius-lg)] border border-[var(--accent)] bg-[rgba(56,189,248,0.08)] px-4 py-3 text-sm font-semibold text-[var(--foreground)] transition-colors hover:bg-[rgba(56,189,248,0.14)] disabled:opacity-55"
          >
            Auto-export to Documents
          </button>
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={onCancel}
          className="mt-4 text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)] disabled:opacity-55"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
