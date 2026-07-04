import { apiFetch } from "@/lib/api";

export type YoutubeAudioJobStatus = "running" | "done" | "error";

export type YoutubeAudioJob = {
  job_id: string;
  status: YoutubeAudioJobStatus;
  progress_percent: number;
  message: string;
  stage?: string | null;
  title?: string | null;
  key?: string | null;
  name?: string | null;
  error?: string | null;
  prefix?: string;
};

export async function startYoutubeAudioDownload(url: string, prefix: string) {
  return apiFetch<{ job_id: string; status: string }>("/api/storage/youtube-audio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, prefix }),
  });
}

export async function fetchYoutubeAudioJob(jobId: string) {
  return apiFetch<YoutubeAudioJob>(
    `/api/storage/youtube-audio/status?job_id=${encodeURIComponent(jobId)}`,
  );
}

export function isYoutubeAudioJobActive(job: YoutubeAudioJob | null | undefined) {
  return job?.status === "running";
}
