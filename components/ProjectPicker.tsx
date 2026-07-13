"use client";

import { useCallback, useEffect, useState } from "react";
import { FolderOpen, Loader2, Plus, Sparkles, Trash2 } from "lucide-react";
import {
  createProject,
  deleteProject,
  fetchProjectList,
  type ProjectSummary,
} from "@/lib/project";
import { useSession } from "@/context/SessionContext";
import { cn } from "@/lib/utils";
import { STATUS_POLL_MS, usePolling } from "@/hooks/usePolling";

const DAY_MS = 24 * 60 * 60 * 1000;

function formatExpiry(expiresAt: number, now: number): string {
  const remaining = expiresAt * 1000 - now;
  if (remaining <= 0) return "Deleting soon";
  const days = Math.floor(remaining / DAY_MS);
  const hours = Math.floor((remaining % DAY_MS) / (60 * 60 * 1000));
  if (days >= 1) return `Auto-deletes in ${days}d ${hours}h`;
  const minutes = Math.floor((remaining % (60 * 60 * 1000)) / (60 * 1000));
  if (hours >= 1) return `Auto-deletes in ${hours}h ${minutes}m`;
  return `Auto-deletes in ${minutes}m`;
}

function stepLabel(project: ProjectSummary) {
  if (project.viewer_ready) return "Ready for b-roll";
  if (project.tts_job?.status === "running") {
    return `Generating voice ${project.tts_job.progress_percent ?? 0}%`;
  }
  if (project.timestamps_job.status === "running") {
    return `Segmenting ${project.timestamps_job.progress_percent ?? 0}%`;
  }
  switch (project.next_step) {
    case "import_script":
      return "Needs script";
    case "import_audio":
      return "Needs audio";
    case "segment_timestamps":
      return "Needs timestamps";
    default:
      return "In progress";
  }
}

export function ProjectPicker() {
  const session = useSession();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const refresh = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const payload = await fetchProjectList();
      setProjects(payload.projects);
    } catch (err) {
      if (!options?.silent) {
        setError(err instanceof Error ? err.message : "Failed to load projects");
        setProjects([]);
      }
    } finally {
      if (!options?.silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  usePolling(() => refresh({ silent: true }), STATUS_POLL_MS);

  const openProject = (project: ProjectSummary) => {
    session.selectProject(project.id, project.name);
  };

  const startNewProject = async () => {
    setBusy(true);
    setError(null);
    try {
      const project = await createProject();
      session.selectProject(project.id, project.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (project: ProjectSummary) => {
    setDeletingId(project.id);
    setError(null);
    try {
      await deleteProject(project.id);
      setConfirmId(null);
      setProjects((prev) => prev.filter((item) => item.id !== project.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className="page-container flex min-h-[calc(100vh-3.5rem)] w-full flex-col justify-center py-10">
      <div className="glow-card w-full p-6 lg:p-8">
        <div className="flex flex-col gap-3">
          <div>
            <h2 className="glow-title text-3xl font-bold tracking-tight">Projects</h2>
            <p className="mt-3 max-w-2xl text-[0.95rem] leading-7 text-[var(--muted)]">
              All progress and files live inside each project. Pick one to continue or start a new
              pipeline.
            </p>
          </div>
        </div>

        <div className="mt-8">
          <button
            type="button"
            className="glow-btn-primary inline-flex w-full items-center justify-center gap-2 px-4 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55 sm:w-auto"
            disabled={busy}
            onClick={() => void startNewProject()}
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            New project
          </button>
        </div>

        {loading ? (
          <p className="mt-8 inline-flex items-center gap-2 text-sm text-[var(--muted)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading projects…
          </p>
        ) : projects.length ? (
          <ul className="mt-8 space-y-3">
            {projects.map((project) => {
              const running = project.timestamps_job.status === "running";
              const expiresAt = project.expires_at ?? null;
              const remainingMs = expiresAt ? expiresAt * 1000 - now : null;
              const expiringSoon = remainingMs != null && remainingMs < DAY_MS;
              const confirming = confirmId === project.id;
              const deleting = deletingId === project.id;
              return (
                <li key={project.id}>
                  <div
                    className={cn(
                      "glow-setup-step flex w-full flex-col gap-2 rounded-[var(--radius-lg)] p-4 transition-colors sm:flex-row sm:items-center",
                      expiringSoon
                        ? "border-[rgba(255,107,107,0.55)] bg-[rgba(255,107,107,0.06)]"
                        : "hover:border-[var(--accent)]",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => openProject(project)}
                      className="flex min-w-0 flex-1 items-start gap-3 text-left"
                    >
                      {project.viewer_ready ? (
                        <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-[var(--accent)]" />
                      ) : (
                        <FolderOpen className="mt-0.5 h-5 w-5 shrink-0 text-[var(--accent)]" />
                      )}
                      <div className="min-w-0">
                        <p className="truncate font-semibold">{project.name}</p>
                        <p className="text-sm text-[var(--muted)]">{stepLabel(project)}</p>
                        {expiresAt ? (
                          <p
                            className={cn(
                              "mt-1 text-[11px]",
                              expiringSoon ? "font-medium text-[#ffb3b3]" : "text-[var(--muted)]/70",
                            )}
                          >
                            {formatExpiry(expiresAt, now)}
                          </p>
                        ) : null}
                        {running ? (
                          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--surface-raised)]">
                            <div
                              className="h-full rounded-full bg-[var(--accent)]"
                              style={{
                                width: `${Math.min(100, Math.max(0, project.timestamps_job.progress_percent ?? 0))}%`,
                              }}
                            />
                          </div>
                        ) : null}
                      </div>
                    </button>
                    <div className="flex items-center gap-3 sm:shrink-0">
                      <span className="text-xs text-[var(--muted)]">
                        {project.viewer_ready
                          ? `${project.aligned_segments}/${project.segment_count} segments`
                          : project.title || project.id.slice(0, 8)}
                      </span>
                      {confirming ? (
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => void handleDelete(project)}
                            disabled={deleting}
                            className="inline-flex items-center gap-1 rounded-[8px] border border-[rgba(255,107,107,0.45)] bg-[rgba(255,107,107,0.12)] px-2.5 py-1.5 text-xs font-semibold text-[#ffc9c9] transition-colors hover:bg-[rgba(255,107,107,0.2)] disabled:opacity-55"
                          >
                            {deleting ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" />
                            )}
                            Delete
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmId(null)}
                            disabled={deleting}
                            className="rounded-[8px] border border-[var(--border)] px-2.5 py-1.5 text-xs font-medium text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmId(project.id)}
                          aria-label={`Delete ${project.name}`}
                          title="Delete project"
                          className="inline-flex h-8 w-8 items-center justify-center rounded-[8px] border border-[var(--border)] text-[var(--muted)] transition-colors hover:border-[rgba(255,107,107,0.5)] hover:text-[#ffc9c9]"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mt-8 text-sm text-[var(--muted)]">
            No projects yet. Create one to import your script and narration.
          </p>
        )}

        {error ? (
          <p className="mt-6 rounded-[10px] border border-[rgba(255,107,107,0.35)] bg-[rgba(255,107,107,0.08)] px-4 py-3 text-sm text-[#ffc9c9]">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
