"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import {
  fetchAutomationStatus,
  resumeAutomation,
  type AutomationStatus,
} from "@/lib/automation";
import { fetchProjectList, type ProjectSummary } from "@/lib/project";
import { progressPercent, stepLabel } from "@/components/ProjectPicker";
import { usePolling } from "@/hooks/usePolling";
import { cn } from "@/lib/utils";

const MONITOR_POLL_MS = 4000;

/**
 * Only surface a job's `error` text when that job is *currently* in a failed
 * state. Job state files keep the last error message around for history even
 * after the job succeeds on a later attempt (e.g. after the orchestrator
 * automatically resumes it) — showing that stale text as if it were live
 * made a fully-recovered, healthy project look broken.
 */
function projectError(project: ProjectSummary): string | null {
  if (project.tts_job?.status === "error" && project.tts_job.error) {
    return project.tts_job.error;
  }
  if (project.timestamps_job?.status === "error" && project.timestamps_job.error) {
    return project.timestamps_job.error;
  }
  const pipelineStatus = project.pipeline_job?.status;
  if (
    (pipelineStatus === "error" || pipelineStatus === "interrupted" || pipelineStatus === "warning") &&
    project.pipeline_job?.error
  ) {
    return project.pipeline_job.error;
  }
  if (project.export_job?.status === "error" && project.export_job.error) {
    return project.export_job.error;
  }
  return null;
}

/** Whether a job is stuck waiting on a restart the automation goal won't trigger on its own. */
function projectStuckOnRestart(project: ProjectSummary): boolean {
  const ttsStuck = project.tts_job?.restart_required && project.tts_job.status !== "running";
  const timestampsStuck =
    project.timestamps_job?.restart_required && project.timestamps_job.status !== "running";
  return Boolean(ttsStuck || timestampsStuck);
}

function projectNeedsAttention(project: ProjectSummary): boolean {
  if (projectError(project)) return true;
  if (project.automation_goal === "none" && projectStuckOnRestart(project)) return true;
  if (project.list_status === "automation_paused") return true;
  return false;
}

function formatTimeAgo(timestamp: number | null | undefined, now: number): string {
  if (!timestamp) return "—";
  const deltaMs = now - timestamp * 1000;
  if (deltaMs < 0) return "just now";
  const seconds = Math.floor(deltaMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function goalLabel(goal: ProjectSummary["automation_goal"]): string {
  switch (goal) {
    case "auto_export":
      return "Auto-export";
    case "fetch_review":
      return "Fetch & review";
    default:
      return "Manual";
  }
}

function statusTone(project: ProjectSummary): "ok" | "warn" | "error" | "idle" {
  if (projectError(project)) return "error";
  if (projectNeedsAttention(project)) return "warn";
  if (project.list_status === "complete") return "ok";
  return "idle";
}

export function ProjectMonitor() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [automation, setAutomation] = useState<AutomationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [resumingAll, setResumingAll] = useState(false);
  const [resumingId, setResumingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [list, status] = await Promise.all([fetchProjectList(), fetchAutomationStatus()]);
      setProjects(list.projects);
      setAutomation(status);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  usePolling(refresh, MONITOR_POLL_MS);

  const handleResumeAll = useCallback(async () => {
    setResumingAll(true);
    try {
      const status = await resumeAutomation();
      setAutomation(status);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resume automation");
    } finally {
      setResumingAll(false);
    }
  }, [refresh]);

  const handleResumeProject = useCallback(
    async (projectId: string) => {
      setResumingId(projectId);
      try {
        const status = await resumeAutomation(projectId);
        setAutomation(status);
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to resume project");
      } finally {
        setResumingId(null);
      }
    },
    [refresh],
  );

  const attentionCount = projects.filter(projectNeedsAttention).length;
  const activeCount = projects.filter(
    (project) => project.list_status && !["complete", "needs_script"].includes(project.list_status),
  ).length;
  const completeCount = projects.filter((project) => project.list_status === "complete").length;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 lg:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--foreground)]">Automation Monitor</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Live status for every project in the pipeline.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleResumeAll()}
          disabled={resumingAll}
          title="Fail-safe: nudge every stuck project forward without waiting"
          className="inline-flex items-center gap-1.5 rounded-[var(--radius-lg)] border border-[var(--border)] px-3 py-2 text-sm font-medium text-[var(--muted)] transition-colors hover:text-[var(--foreground)] disabled:opacity-55"
        >
          {resumingAll ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Resume all
        </button>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard label="Total projects" value={projects.length} />
        <SummaryCard label="Active" value={activeCount} />
        <SummaryCard label="Complete" value={completeCount} />
        <SummaryCard
          label="Needs attention"
          value={attentionCount}
          tone={attentionCount > 0 ? "error" : "ok"}
        />
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-4 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3 text-sm">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 font-medium",
            automation?.enabled ? "text-emerald-400" : "text-amber-400",
          )}
        >
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              automation?.enabled ? "bg-emerald-400" : "bg-amber-400",
            )}
          />
          Automation {automation?.enabled ? "enabled" : "paused"}
        </span>
        <span className="text-[var(--muted)]">
          Export queue: {automation?.queue_length ?? 0}
          {automation?.exporting_project_id ? " (1 exporting)" : ""}
        </span>
        <span className="text-[var(--muted)]">
          Last scan: {formatTimeAgo(automation?.last_scan_at, now)}
        </span>
      </div>

      {error ? (
        <div className="mb-4 rounded-[var(--radius-lg)] border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-[var(--muted)]">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : projects.length === 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-8 text-center text-sm text-[var(--muted)]">
          No projects yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-[var(--surface-raised)] text-xs uppercase tracking-wide text-[var(--muted)]">
              <tr>
                <th className="px-4 py-3 font-medium">Project</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Progress</th>
                <th className="px-4 py-3 font-medium">Goal</th>
                <th className="px-4 py-3 font-medium">Updated</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {projects.map((project) => {
                const tone = statusTone(project);
                const pct = progressPercent(project);
                const err = projectError(project);
                const updatedAt =
                  project.tts_job?.updated_at ??
                  project.timestamps_job?.updated_at ??
                  project.pipeline_job?.updated_at ??
                  project.last_activity ??
                  null;
                return (
                  <tr key={project.id} className="align-top">
                    <td className="px-4 py-3">
                      <div className="font-medium text-[var(--foreground)]">
                        {project.title || project.name}
                      </div>
                      <div className="text-xs text-[var(--muted)]">{project.name}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div
                        className={cn(
                          "inline-flex items-center gap-1.5 font-medium",
                          tone === "error" && "text-red-400",
                          tone === "warn" && "text-amber-400",
                          tone === "ok" && "text-emerald-400",
                          tone === "idle" && "text-[var(--muted)]",
                        )}
                      >
                        {tone === "error" ? (
                          <AlertTriangle className="h-3.5 w-3.5" />
                        ) : tone === "ok" ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : null}
                        {stepLabel(project)}
                      </div>
                      {err ? (
                        <div className="mt-1 max-w-xs truncate text-xs text-red-300" title={err}>
                          {err}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      {pct != null ? (
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-[var(--surface-raised)]">
                            <div
                              className="h-full rounded-full bg-emerald-400"
                              style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
                            />
                          </div>
                          <span className="text-xs text-[var(--muted)]">{pct}%</span>
                        </div>
                      ) : (
                        <span className="text-xs text-[var(--muted)]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--muted)]">
                      {goalLabel(project.automation_goal)}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--muted)]">
                      {formatTimeAgo(updatedAt, now)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => void handleResumeProject(project.id)}
                        disabled={resumingId === project.id}
                        title="Fail-safe: nudge this project forward if automation got stuck"
                        className="inline-flex items-center gap-1.5 rounded-[8px] border border-[var(--border)] px-2.5 py-1.5 text-xs font-medium text-[var(--muted)] transition-colors hover:text-[var(--foreground)] disabled:opacity-55"
                      >
                        {resumingId === project.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3.5 w-3.5" />
                        )}
                        Resume
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "ok" | "error";
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div
        className={cn(
          "mt-1 text-2xl font-semibold",
          tone === "error" ? "text-red-400" : tone === "ok" ? "text-emerald-400" : "text-[var(--foreground)]",
        )}
      >
        {value}
      </div>
    </div>
  );
}
