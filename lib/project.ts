import { apiFetch, invalidateBackendUrlCache, uploadFormData } from "@/lib/api";
import type { ScriptFormat, RemotionScriptSummary } from "@/lib/types";

export type TimestampAlignment = {
  total_segments: number;
  aligned_segments: number;
  timed_segments: number;
  interpolated_segments?: number;
  estimated_segments?: number;
  total_duration_seconds?: number;
  total_duration_timecode?: string;
  whisper_model?: string;
};

export type TranscriptPreview = {
  transcript: string;
  segment_count: number;
  word_count: number;
  estimated_duration_seconds: number;
  estimated_duration_label: string;
  wpm?: number;
};

export type TtsJobStatus = {
  status: "idle" | "running" | "done" | "error";
  message: string;
  error: string | null;
  progress_percent?: number;
  stage?: string;
  started_at?: number | null;
  updated_at?: number | null;
  restart_required?: boolean;
  chunk_total?: number;
  chunk_done?: number;
  word_count?: number;
  estimated_duration_seconds?: number;
  estimated_duration_label?: string;
  logs?: Array<{
    ts: number;
    message: string;
    stage: string;
    progress_percent: number;
  }>;
};

export type ProjectStatus = {
  workspace: string;
  project_id?: string | null;
  script_uploaded: boolean;
  script_format?: ScriptFormat | null;
  remotion?: RemotionScriptSummary | null;
  remotion_runtime_ready?: boolean;
  audio_uploaded: boolean;
  timestamps_ready: boolean;
  viewer_ready: boolean;
  title: string | null;
  segment_count: number;
  aligned_segments: number;
  timed_segments?: number;
  timestamp_alignment?: TimestampAlignment | null;
  next_step: "import_script" | "import_audio" | "segment_timestamps" | "viewer";
  transcript_preview?: TranscriptPreview | null;
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
    alignment_summary?: TimestampAlignment | null;
    logs?: Array<{
      ts: number;
      message: string;
      stage: string;
      progress_percent: number;
    }>;
  };
  tts_job: TtsJobStatus;
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

/** Resolve where large audio uploads should go (direct tunnel vs local proxy). */
let cachedAudioUploadUrl: string | null | undefined;

export function invalidateAudioUploadUrlCache() {
  cachedAudioUploadUrl = undefined;
  invalidateBackendUrlCache();
}

async function resolveAudioUploadUrl(): Promise<string> {
  if (cachedAudioUploadUrl !== undefined) {
    return cachedAudioUploadUrl ?? "/api/project/upload/audio";
  }
  try {
    const config = await fetch("/api/config", { cache: "no-store" }).then(
      (response) => response.json() as Promise<{ audio_upload_url?: string | null }>,
    );
    cachedAudioUploadUrl = config.audio_upload_url ?? null;
  } catch {
    cachedAudioUploadUrl = null;
  }
  return cachedAudioUploadUrl ?? "/api/project/upload/audio";
}

export async function uploadAudioFile(
  file: File,
  onProgress?: (percent: number) => void,
) {
  const form = new FormData();
  form.append("file", file);
  const url = await resolveAudioUploadUrl();
  return uploadFormData<ProjectStatus>(url, form, onProgress);
}

export async function uploadTimestampsFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<ProjectStatus>("/api/project/upload/timestamps", {
    method: "POST",
    body: form,
  });
}

export async function startSegmentTimestamps(
  model = "medium",
  options?: { retranscribe?: boolean },
) {
  return apiFetch<ProjectStatus["timestamps_job"]>("/api/project/segment-timestamps", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, retranscribe: options?.retranscribe ?? false }),
  });
}

export async function fetchSegmentTimestampsStatus() {
  return apiFetch<ProjectStatus["timestamps_job"]>("/api/project/segment-timestamps/status");
}

export async function startAudioGeneration() {
  return apiFetch<TtsJobStatus>("/api/project/generate-audio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export async function fetchAudioGenerationStatus() {
  return apiFetch<TtsJobStatus>("/api/project/generate-audio/status");
}

export async function cancelAudioGeneration(reason = "Cancelled.") {
  return apiFetch<TtsJobStatus>("/api/project/generate-audio/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
}

export type ProjectSummary = {
  id: string;
  name: string;
  created_at?: number | null;
  updated_at?: number | null;
  last_activity?: number | null;
  expires_at?: number | null;
  ttl_seconds?: number;
  viewer_ready: boolean;
  next_step: ProjectStatus["next_step"];
  title: string | null;
  segment_count: number;
  aligned_segments: number;
  timestamps_job: ProjectStatus["timestamps_job"];
  tts_job: TtsJobStatus;
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

export async function deleteProject(projectId: string) {
  return apiFetch<{ ok: boolean; deleted: string }>("/api/project/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
}
