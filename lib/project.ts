import { apiFetch, getBrollBackendUrl } from "@/lib/api";

export type ProjectStatus = {
  workspace: string;
  project_id?: string | null;
  script_uploaded: boolean;
  audio_uploaded: boolean;
  timestamps_ready: boolean;
  viewer_ready: boolean;
  title: string | null;
  segment_count: number;
  aligned_segments: number;
  next_step: "import_script" | "import_audio" | "segment_timestamps" | "viewer";
  timestamps_job: {
    status: "idle" | "running" | "done" | "error";
    message: string;
    error: string | null;
    progress_percent?: number;
    stage?: string;
    started_at?: number | null;
    updated_at?: number | null;
    restart_required?: boolean;
    hardware?: SegmentationHardware | null;
    logs?: Array<{
      ts: number;
      message: string;
      stage: string;
      progress_percent: number;
    }>;
  };
};

export type SegmentationHardware = {
  device: string;
  gpu_name?: string | null;
  cuda_available?: boolean;
  cuda_version?: string | null;
  torch_version?: string | null;
  hint?: string | null;
  gpu_util_percent?: number | null;
  gpu_memory_used_mb?: number | null;
  gpu_memory_total_mb?: number | null;
  torch_memory_used_mb?: number | null;
  cpu_percent?: number | null;
  ram_used_mb?: number | null;
  ram_total_mb?: number | null;
};

export async function fetchWhisperHardware() {
  return apiFetch<SegmentationHardware>("/api/whisper/hardware");
}

export async function fetchProjectStatus() {
  return apiFetch<ProjectStatus>("/api/project/status");
}

export async function uploadScriptFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ProjectStatus>("/api/project/upload/script", {
    method: "POST",
    body: form,
  });
}

export async function uploadAudioFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  // Upload directly to Python — avoids Next.js rewrite proxy 100MB body cap.
  return apiFetch<ProjectStatus>(`${getBrollBackendUrl()}/api/project/upload/audio`, {
    method: "POST",
    body: form,
  });
}

export async function uploadTimestampsFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ProjectStatus>("/api/project/upload/timestamps", {
    method: "POST",
    body: form,
  });
}

export async function startSegmentTimestamps(model = "small") {
  return apiFetch<ProjectStatus["timestamps_job"]>("/api/project/segment-timestamps", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
}

export async function fetchSegmentTimestampsStatus() {
  return apiFetch<ProjectStatus["timestamps_job"]>("/api/project/segment-timestamps/status");
}

export type ProjectSummary = {
  id: string;
  name: string;
  created_at?: number | null;
  updated_at?: number | null;
  viewer_ready: boolean;
  next_step: ProjectStatus["next_step"];
  title: string | null;
  segment_count: number;
  aligned_segments: number;
  timestamps_job: ProjectStatus["timestamps_job"];
};

export async function fetchProjectList() {
  return apiFetch<{
    projects: ProjectSummary[];
    has_running_job: boolean;
    running_project: { id: string; name: string } | null;
  }>("/api/project/list");
}

export async function createProject(name?: string) {
  return apiFetch<ProjectSummary>("/api/project/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name || undefined }),
  });
}
