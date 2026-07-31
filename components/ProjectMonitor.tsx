"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Loader2,
  Mic,
  Pause,
  RefreshCw,
  Scissors,
  Upload,
  Video,
} from "lucide-react";
import {
  fetchAutomationStatus,
  resumeAutomation,
  type AutomationStatus,
} from "@/lib/automation";
import { fetchProjectList, type ProjectSummary } from "@/lib/project";
import { usePolling } from "@/hooks/usePolling";
import { cn } from "@/lib/utils";

const MONITOR_POLL_MS = 4000;

type StageTone = "done" | "active" | "error" | "pending";
type StageKey = "script" | "voice" | "timestamps" | "broll" | "export";

type Stage = {
  key: StageKey;
  label: string;
  icon: typeof Upload;
  tone: StageTone;
};

/**
 * Only surface a job's `error` text when that job is *currently* in a failed
 * state — job state files keep the last error message around for history,
 * and showing it once the job has actually moved on made a healthy,
 * self-recovered project look permanently broken.
 */
function jobError(project: ProjectSummary): { stage: StageKey; message: string } | null {
  if (project.tts_job?.status === "error" && project.tts_job.error) {
    return { stage: "voice", message: project.tts_job.error };
  }
  if (project.timestamps_job?.status === "error" && project.timestamps_job.error) {
    return { stage: "timestamps", message: project.timestamps_job.error };
  }
  const pipelineStatus = project.pipeline_job?.status;
  if (
    (pipelineStatus === "error" || pipelineStatus === "interrupted" || pipelineStatus === "warning") &&
    project.pipeline_job?.error
  ) {
    return { stage: "broll", message: project.pipeline_job.error };
  }
  if (project.export_job?.status === "error" && project.export_job.error) {
    return { stage: "export", message: project.export_job.error };
  }
  return null;
}

/** A job stuck waiting on a restart that a "none" automation goal will never trigger on its own. */
function stuckOnRestart(project: ProjectSummary): boolean {
  const ttsStuck = project.tts_job?.restart_required && project.tts_job.status !== "running";
  const timestampsStuck =
    project.timestamps_job?.restart_required && project.timestamps_job.status !== "running";
  return Boolean(ttsStuck || timestampsStuck);
}

/** Does this project require the user to click Resume themselves (automation won't touch it)? */
function needsManualNudge(project: ProjectSummary): boolean {
  if (project.list_status === "automation_paused") return true;
  return project.automation_goal === "none" && stuckOnRestart(project);
}

function buildStages(project: ProjectSummary): Stage[] {
  const ls = project.list_status ?? "";
  const err = jobError(project);

  const scriptDone = ls !== "needs_script";

  const voiceActive = ls === "generating_voice";
  const voiceDone = scriptDone && ls !== "needs_audio" && !voiceActive;

  const timestampsActive = ls === "segmenting";
  const timestampsDone = voiceDone && ls !== "needs_timestamps" && !timestampsActive;

  const brollPendingStates = new Set(["ready_for_broll", "fetching_broll", "clearing_duplicates", "ready_for_refetch"]);
  const brollActive = ls === "fetching_broll" || ls === "clearing_duplicates";
  const brollDone = timestampsDone && !brollPendingStates.has(ls);

  const exportActive = ls === "exporting" || ls === "queued_for_export";
  const exportDone = ls === "complete";

  const toneFor = (
    stageKey: StageKey,
    started: boolean,
    done: boolean,
    active: boolean,
  ): StageTone => {
    if (err?.stage === stageKey) return "error";
    if (done) return "done";
    if (active) return "active";
    if (!started) return "pending";
    return "pending";
  };

  return [
    { key: "script", label: "Script", icon: Upload, tone: scriptDone ? "done" : "active" },
    { key: "voice", label: "Voice", icon: Mic, tone: toneFor("voice", scriptDone, voiceDone, voiceActive) },
    {
      key: "timestamps",
      label: "Timestamps",
      icon: Scissors,
      tone: toneFor("timestamps", voiceDone, timestampsDone, timestampsActive),
    },
    {
      key: "broll",
      label: "B-Roll",
      icon: Video,
      tone: toneFor("broll", timestampsDone, brollDone, brollActive),
    },
    {
      key: "export",
      label: "Export",
      icon: CheckCircle2,
      tone: toneFor("export", brollDone, exportDone, exportActive),
    },
  ];
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

/** One clear, plain-language sentence describing what's happening right now. */
function headline(
  project: ProjectSummary,
  automation: AutomationStatus | null,
): { text: string; tone: StageTone } {
  const ls = project.list_status ?? "";
  const err = jobError(project);

  if (err) return { text: err.message, tone: "error" };

  switch (ls) {
    case "complete":
      return { text: "Done — exported successfully.", tone: "done" };
    case "exporting":
      return { text: `Exporting now (${project.export_job?.progress_percent ?? 0}%)…`, tone: "active" };
    case "queued_for_export": {
      const queue = automation?.queued_project_ids ?? [];
      const idx = queue.indexOf(project.id);
      const position = idx >= 0 ? idx + 1 + (automation?.exporting_project_id ? 1 : 0) : null;
      const total = queue.length + (automation?.exporting_project_id ? 1 : 0);
      return {
        text:
          position != null
            ? `Waiting in the export queue — position ${position} of ${total}.`
            : "Waiting for its turn to export…",
        tone: "active",
      };
    }
    case "ready_for_export":
      return project.automation_goal === "auto_export"
        ? { text: "B-roll ready — about to be queued for export…", tone: "active" }
        : { text: "Ready to export whenever you are.", tone: "pending" };
    case "ready_for_refetch":
      return { text: "Waiting for you to review and refetch at least one clip.", tone: "pending" };
    case "clearing_duplicates": {
      const cleared = project.pipeline_job?.cleared ?? 0;
      const total = project.pipeline_job?.clear_total ?? 0;
      return {
        text: total > 0 ? `Clearing duplicate clips (${cleared}/${total})…` : "Clearing duplicate clips…",
        tone: "active",
      };
    }
    case "fetching_broll": {
      const done = project.pipeline_job?.done ?? project.broll_fetched ?? 0;
      const total = project.pipeline_job?.total ?? project.broll_total ?? 0;
      return {
        text: total > 0 ? `Fetching b-roll clips (${done}/${total})…` : "Fetching b-roll clips…",
        tone: "active",
      };
    }
    case "ready_for_broll":
      return { text: "Starting b-roll fetch…", tone: "active" };
    case "segmenting":
      return { text: `Transcribing audio (${project.timestamps_job?.progress_percent ?? 0}%)…`, tone: "active" };
    case "needs_timestamps":
      return project.automation_goal === "none"
        ? { text: "Waiting for you to start transcription (automation is off).", tone: "pending" }
        : { text: "Waiting to start transcription…", tone: "pending" };
    case "generating_voice":
      return { text: `Generating narration (${project.tts_job?.progress_percent ?? 0}%)…`, tone: "active" };
    case "needs_audio":
      return { text: "Waiting to generate narration…", tone: "pending" };
    case "needs_script":
      return { text: "Needs a script uploaded to begin.", tone: "pending" };
    case "automation_paused":
      return { text: "Automation is paused — enable it or resume this project manually.", tone: "pending" };
    default:
      return { text: "In progress…", tone: "active" };
  }
}

const stageDotClasses: Record<StageTone, string> = {
  done: "border-emerald-400 bg-emerald-400/20 text-emerald-400",
  active: "border-sky-400 bg-sky-400/20 text-sky-400",
  error: "border-red-400 bg-red-400/20 text-red-400",
  pending: "border-[var(--border)] bg-[var(--surface-raised)] text-[var(--muted)]",
};

const headlineTextClasses: Record<StageTone, string> = {
  done: "text-emerald-400",
  active: "text-sky-400",
  error: "text-red-400",
  pending: "text-[var(--muted)]",
};

function StageStepper({ stages }: { stages: Stage[] }) {
  return (
    <div className="flex items-center gap-1">
      {stages.map((stage, index) => {
        const Icon = stage.icon;
        return (
          <div key={stage.key} className="flex items-center gap-1">
            <div className="flex flex-col items-center gap-1" title={stage.label}>
              <div
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full border transition-colors",
                  stageDotClasses[stage.tone],
                )}
              >
                {stage.tone === "active" ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Icon className="h-3.5 w-3.5" />
                )}
              </div>
              <span className="text-[10px] font-medium text-[var(--muted)]">{stage.label}</span>
            </div>
            {index < stages.length - 1 ? (
              <ChevronRight className="mb-4 h-3.5 w-3.5 shrink-0 text-[var(--border)]" />
            ) : null}
          </div>
        );
      })}
    </div>
  );
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

  const errorCount = projects.filter((project) => jobError(project) != null).length;
  const waitingOnYouCount = projects.filter(needsManualNudge).length;
  const activeCount = projects.filter(
    (project) => project.list_status && !["complete", "needs_script"].includes(project.list_status),
  ).length;
  const completeCount = projects.filter((project) => project.list_status === "complete").length;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 lg:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--foreground)]">Automation Monitor</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Plain-language status for every project — no guessing required.
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

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <SummaryCard label="Total" value={projects.length} />
        <SummaryCard label="In progress" value={activeCount} tone="active" />
        <SummaryCard label="Complete" value={completeCount} tone="ok" />
        <SummaryCard
          label="Waiting on you"
          value={waitingOnYouCount}
          tone={waitingOnYouCount > 0 ? "warn" : "ok"}
        />
        <SummaryCard label="Errors" value={errorCount} tone={errorCount > 0 ? "error" : "ok"} />
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
          Automation {automation?.enabled ? "is running" : "is paused"}
        </span>
        <span className="inline-flex items-center gap-1.5 text-[var(--muted)]">
          <Video className="h-3.5 w-3.5" />
          {automation?.exporting_project_id
            ? `Exporting 1 now, ${automation.queue_length} waiting`
            : automation?.queue_length
              ? `${automation.queue_length} waiting to export`
              : "Export queue is empty"}
        </span>
        <span className="inline-flex items-center gap-1.5 text-[var(--muted)]">
          <Clock className="h-3.5 w-3.5" />
          Checked {formatTimeAgo(automation?.last_scan_at, now)}
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
        <div className="flex flex-col gap-3">
          {projects.map((project) => {
            const stages = buildStages(project);
            const head = headline(project, automation);
            const nudge = needsManualNudge(project);
            const isResuming = resumingId === project.id;

            return (
              <div
                key={project.id}
                className={cn(
                  "rounded-[var(--radius-lg)] border bg-[var(--surface-raised)] px-4 py-4",
                  head.tone === "error"
                    ? "border-red-500/30"
                    : nudge
                      ? "border-amber-500/30"
                      : "border-[var(--border)]",
                )}
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate font-medium text-[var(--foreground)]">
                        {project.title || project.name}
                      </h3>
                      <span className="shrink-0 rounded-full border border-[var(--border)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--muted)]">
                        {goalLabel(project.automation_goal)}
                      </span>
                    </div>
                    <div
                      className={cn(
                        "mt-1.5 flex items-center gap-1.5 text-sm font-medium",
                        headlineTextClasses[head.tone],
                      )}
                    >
                      {head.tone === "error" ? (
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                      ) : head.tone === "done" ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0" />
                      ) : nudge ? (
                        <Pause className="h-4 w-4 shrink-0" />
                      ) : null}
                      <span>{head.text}</span>
                    </div>
                    <div className="mt-1 text-xs text-[var(--muted)]">
                      Last activity {formatTimeAgo(project.last_activity, now)}
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <StageStepper stages={stages} />
                    <button
                      type="button"
                      onClick={() => void handleResumeProject(project.id)}
                      disabled={isResuming}
                      title="Fail-safe: nudge this project forward if automation got stuck"
                      className={cn(
                        "inline-flex shrink-0 items-center gap-1.5 rounded-[8px] border px-2.5 py-1.5 text-xs font-medium transition-colors disabled:opacity-55",
                        nudge
                          ? "border-amber-500/40 text-amber-300 hover:bg-amber-500/10"
                          : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]",
                      )}
                    >
                      {isResuming ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="h-3.5 w-3.5" />
                      )}
                      Resume
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
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
  tone?: "neutral" | "ok" | "warn" | "error" | "active";
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div
        className={cn(
          "mt-1 text-2xl font-semibold",
          tone === "error"
            ? "text-red-400"
            : tone === "warn"
              ? "text-amber-400"
              : tone === "ok"
                ? "text-emerald-400"
                : tone === "active"
                  ? "text-sky-400"
                  : "text-[var(--foreground)]",
        )}
      >
        {value}
      </div>
    </div>
  );
}
