import { apiFetch } from "@/lib/api";

export type ActivityJobType = "whisper" | "export" | "youtube_audio";

export interface ActivityJob {
  type: ActivityJobType;
  label: string;
  job_id?: string | null;
  project_id: string | null;
  project_name: string | null;
  progress_percent: number;
  message: string;
  stage?: string | null;
  eta_seconds?: number | null;
}

export interface ActivityGpu {
  name: string | null;
  utilization_percent: number | null;
  memory_used_mb: number | null;
  memory_total_mb: number | null;
}

export interface ActivitySnapshot {
  jobs: ActivityJob[];
  gpu: ActivityGpu | null;
  busy: boolean;
}

export async function fetchActivity(): Promise<ActivitySnapshot> {
  return apiFetch<ActivitySnapshot>("/api/activity");
}
