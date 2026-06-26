"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, FolderOpen, HardDrive, Loader2, X } from "lucide-react";
import type {
  FolderFetchAssignment,
  FolderFetchPlan,
  FolderShortageStrategy,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type FolderFetchModalProps = {
  open: boolean;
  busy: boolean;
  plan: FolderFetchPlan | null;
  error: string | null;
  onClose: () => void;
  onConfirm: (strategy?: FolderShortageStrategy) => void;
  onReload: (strategy?: FolderShortageStrategy) => void;
};

const STRATEGY_OPTIONS: Array<{
  id: FolderShortageStrategy;
  title: string;
  description: string;
}> = [
  {
    id: "leave_empty",
    title: "Leave extras empty",
    description:
      "Use each folder clip once, in order. Segments without a clip stay empty for you to fill manually.",
  },
  {
    id: "reuse_spaced",
    title: "Reuse clips with spacing",
    description:
      "Reuse folder clips when needed, but never within 5 minutes of timeline between uses of the same clip.",
  },
  {
    id: "random_api",
    title: "API fetch for extras",
    description:
      "Use folder clips first, then randomly fetch from the API using each segment's search term.",
  },
];

function modeLabel(mode: FolderFetchAssignment["mode"]) {
  switch (mode) {
    case "folder":
      return "Folder";
    case "api":
      return "API (stock)";
    case "api_warning":
      return "API (no folder)";
    case "api_shortage":
      return "API (shortage)";
    case "unassigned":
      return "Empty";
    default:
      return mode;
  }
}

function modeClass(mode: FolderFetchAssignment["mode"]) {
  switch (mode) {
    case "folder":
      return "text-emerald-200 bg-emerald-500/15 border-emerald-500/30";
    case "api":
      return "text-sky-200 bg-sky-500/15 border-sky-500/30";
    case "api_warning":
    case "api_shortage":
      return "text-amber-200 bg-amber-500/15 border-amber-500/30";
    case "unassigned":
      return "text-[var(--muted)] bg-[var(--surface-raised)] border-[var(--border)]";
    default:
      return "text-[var(--muted)] bg-[var(--surface-raised)] border-[var(--border)]";
  }
}

export function FolderFetchModal({
  open,
  busy,
  plan,
  error,
  onClose,
  onConfirm,
  onReload,
}: FolderFetchModalProps) {
  const [filter, setFilter] = useState<"" | FolderFetchAssignment["mode"]>("");
  const [shortageStrategy, setShortageStrategy] = useState<FolderShortageStrategy | "">(
    "",
  );

  useEffect(() => {
    if (!open) {
      setFilter("");
      setShortageStrategy("");
    }
  }, [open]);

  useEffect(() => {
    if (plan?.shortage_strategy) {
      setShortageStrategy(plan.shortage_strategy);
    }
  }, [plan?.shortage_strategy]);

  const assignments = plan?.assignments ?? [];
  const visible = useMemo(() => {
    if (!filter) return assignments;
    return assignments.filter((item) => item.mode === filter);
  }, [assignments, filter]);

  const folderEntries = useMemo(() => {
    if (!plan?.folders) return [];
    return Object.entries(plan.folders).sort(([a], [b]) => a.localeCompare(b));
  }, [plan?.folders]);

  if (!open) return null;

  const summary = plan?.summary;
  const needsShortageChoice = Boolean(plan?.needs_shortage_choice);
  const activeStrategy =
    (shortageStrategy || plan?.shortage_strategy || undefined) as
      | FolderShortageStrategy
      | undefined;
  const canConfirm = Boolean(
    summary &&
      (summary.folder > 0 || (summary.api_shortage ?? 0) > 0) &&
      (!needsShortageChoice || activeStrategy),
  );

  const handleStrategyChange = (strategy: FolderShortageStrategy) => {
    setShortageStrategy(strategy);
    onReload(strategy);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      onClick={() => {
        if (!busy) onClose();
      }}
    >
      <div
        className="glow-card flex max-h-[90vh] w-full max-w-4xl flex-col rounded-[var(--radius-lg)]"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="folder-fetch-title"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
          <div className="min-w-0">
            <h2 id="folder-fetch-title" className="text-lg font-semibold">
              Folder Fetch
            </h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Assign clips from your B-Roll storage folders to matching segment types.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="glow-btn-secondary rounded-[var(--radius-sm)] p-2 disabled:opacity-55"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 overflow-y-auto px-5 py-4">
          {error ? (
            <div className="rounded-[var(--radius)] border border-red-500/35 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          ) : null}

          {!plan && !error ? (
            <div className="flex items-center gap-2 py-8 text-sm text-[var(--muted)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading folder assignments…
            </div>
          ) : null}

          {plan?.shortages && plan.shortages.length > 0 ? (
            <div className="rounded-[var(--radius)] border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              <p className="font-medium">Not enough clips in some folders</p>
              <ul className="mt-2 space-y-1 text-[var(--muted)]">
                {plan.shortages.map((shortage) => (
                  <li key={shortage.category}>
                    <span className="text-[var(--foreground)]">{shortage.category}</span>:{" "}
                    {shortage.clip_count} clip{shortage.clip_count === 1 ? "" : "s"} for{" "}
                    {shortage.segment_count} segments ({shortage.deficit} short)
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {needsShortageChoice ? (
            <div className="space-y-3">
              <p className="text-sm font-medium text-[var(--foreground)]">
                How should extras be handled?
              </p>
              <div className="grid gap-2">
                {STRATEGY_OPTIONS.map((option) => {
                  const selected = shortageStrategy === option.id;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      disabled={busy}
                      onClick={() => handleStrategyChange(option.id)}
                      className={cn(
                        "rounded-[var(--radius)] border px-4 py-3 text-left transition-colors disabled:opacity-55",
                        selected
                          ? "border-[var(--accent)] bg-[rgba(229,229,229,0.08)]"
                          : "border-[var(--border)] bg-[var(--surface-raised)] hover:bg-[var(--surface)]",
                      )}
                    >
                      <p className="text-sm font-semibold">{option.title}</p>
                      <p className="mt-1 text-sm text-[var(--muted)]">{option.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          {summary ? (
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <div className="rounded-[var(--radius)] border border-emerald-500/30 bg-emerald-500/10 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.08em] text-emerald-200/80">Folder</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{summary.folder}</p>
              </div>
              <div className="rounded-[var(--radius)] border border-sky-500/30 bg-sky-500/10 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.08em] text-sky-200/80">Stock (API)</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{summary.api}</p>
              </div>
              <div className="rounded-[var(--radius)] border border-amber-500/30 bg-amber-500/10 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.08em] text-amber-200/80">API warning</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{summary.api_warning}</p>
              </div>
              <div className="rounded-[var(--radius)] border border-amber-500/30 bg-amber-500/10 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.08em] text-amber-200/80">API shortage</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">
                  {summary.api_shortage ?? 0}
                </p>
              </div>
              <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.08em] text-[var(--muted)]">Empty</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">
                  {summary.unassigned ?? 0}
                </p>
              </div>
            </div>
          ) : null}

          {folderEntries.length > 0 ? (
            <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                Storage folders
              </p>
              <ul className="mt-2 space-y-1 text-sm">
                {folderEntries.map(([category, info]) => (
                  <li key={category} className="flex items-center gap-2">
                    <FolderOpen className="h-3.5 w-3.5 text-[var(--muted)]" />
                    <span className="font-medium">{info.prefix}</span>
                    <span className="text-[var(--muted)]">
                      {info.clip_count} clip{info.clip_count === 1 ? "" : "s"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {summary && summary.api_warning > 0 ? (
            <div className="flex items-start gap-2 rounded-[var(--radius)] border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                {summary.api_warning} segment
                {summary.api_warning === 1 ? "" : "s"} have no matching B-Roll folder. Use manual
                fetch or upload clips first.
              </p>
            </div>
          ) : null}

          {assignments.length > 0 && (!needsShortageChoice || activeStrategy) ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <label className="text-sm text-[var(--muted)]">Show</label>
                <select
                  value={filter}
                  onChange={(event) =>
                    setFilter(event.target.value as "" | FolderFetchAssignment["mode"])
                  }
                  className="glow-control rounded-[10px] px-3 py-2 text-sm"
                  disabled={busy}
                >
                  <option value="">All assignments</option>
                  <option value="folder">Folder only</option>
                  <option value="unassigned">Empty</option>
                  <option value="api">Stock (API)</option>
                  <option value="api_shortage">API shortage</option>
                  <option value="api_warning">API warning</option>
                </select>
                {activeStrategy ? (
                  <button
                    type="button"
                    onClick={() => onReload(activeStrategy)}
                    disabled={busy}
                    className="glow-btn-secondary rounded-[10px] px-3 py-2 text-sm font-semibold disabled:opacity-55"
                  >
                    Refresh preview
                  </button>
                ) : null}
              </div>

              <div className="max-h-[42vh] overflow-y-auto rounded-[var(--radius)] border border-[var(--border)]">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 bg-[var(--surface)] text-xs uppercase tracking-[0.06em] text-[var(--muted)]">
                    <tr>
                      <th className="px-3 py-2 font-semibold">#</th>
                      <th className="px-3 py-2 font-semibold">Type</th>
                      <th className="px-3 py-2 font-semibold">Mode</th>
                      <th className="px-3 py-2 font-semibold">Assignment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((item) => (
                      <tr
                        key={item.segment_id}
                        className="border-t border-[var(--border)] align-top"
                      >
                        <td className="px-3 py-2 tabular-nums">{item.segment_id}</td>
                        <td className="px-3 py-2">{item.category}</td>
                        <td className="px-3 py-2">
                          <span
                            className={cn(
                              "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium",
                              modeClass(item.mode),
                            )}
                          >
                            {modeLabel(item.mode)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-[var(--muted)]">
                          {item.mode === "folder" ? (
                            <span className="inline-flex items-center gap-1.5 text-[var(--foreground)]">
                              <HardDrive className="h-3.5 w-3.5" />
                              {item.clip_name}
                              {item.reused ? (
                                <span className="text-xs text-amber-200">(reused)</span>
                              ) : null}
                            </span>
                          ) : item.warning ? (
                            <span className="text-amber-100">{item.warning}</span>
                          ) : (
                            <span>API search: {item.search_query || "—"}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-[var(--border)] px-5 py-4 sm:flex-row sm:justify-end">
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
            onClick={() => onConfirm(activeStrategy)}
            disabled={busy || !canConfirm}
            className="glow-btn-primary inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
            title={
              canConfirm
                ? undefined
                : needsShortageChoice
                  ? "Choose how to handle folder shortages first."
                  : "Upload clips into B-Roll/<type>/ folders to enable folder assignments."
            }
          >
            {busy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Assigning…
              </>
            ) : (
              <>
                <FolderOpen className="h-4 w-4" />
                Confirm assignments
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
