"use client";

import { useCallback, useEffect, useState } from "react";
import { FolderOpen, Loader2, Plus, Sparkles } from "lucide-react";
import { createProject, fetchProjectList, type ProjectSummary } from "@/lib/project";
import { useSession } from "@/context/SessionContext";

function stepLabel(project: ProjectSummary) {
  if (project.viewer_ready) return "Ready for b-roll";
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

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchProjectList();
      setProjects(payload.projects);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

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
              return (
                <li key={project.id}>
                  <button
                    type="button"
                    onClick={() => openProject(project)}
                    className="glow-setup-step flex w-full flex-col gap-2 rounded-[var(--radius-lg)] p-4 text-left transition-colors hover:border-[var(--accent)] sm:flex-row sm:items-center"
                  >
                    <div className="flex min-w-0 flex-1 items-start gap-3">
                      {project.viewer_ready ? (
                        <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-[var(--accent)]" />
                      ) : (
                        <FolderOpen className="mt-0.5 h-5 w-5 shrink-0 text-[var(--accent)]" />
                      )}
                      <div className="min-w-0">
                        <p className="truncate font-semibold">{project.name}</p>
                        <p className="text-sm text-[var(--muted)]">{stepLabel(project)}</p>
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
                    </div>
                    <span className="text-xs text-[var(--muted)] sm:shrink-0">
                      {project.viewer_ready
                        ? `${project.aligned_segments}/${project.segment_count} segments`
                        : project.title || project.id.slice(0, 8)}
                    </span>
                  </button>
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
