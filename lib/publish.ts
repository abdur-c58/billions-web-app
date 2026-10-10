import { apiFetch } from "@/lib/api";
import type { ScriptThumbnail } from "@/lib/types";

export type PublishCheck = {
  key: string;
  label: string;
  ok: boolean;
  detail: string;
};

export type PublishState = "ready" | "not_ready" | "published";

export type PublishVideo = {
  project_id: string;
  project_name: string;
  title: string;
  channel: string;
  video_path: string;
  video_exists: boolean;
  video_size_bytes: number;
  exported_at: number | null;
  thumbnail: ScriptThumbnail | null;
  thumbnail_prompt: string;
  chapters: { title: string; timestamp: string; start_seconds: number }[];
  chapters_text: string;
  checks: PublishCheck[];
  ready_for_publishing: boolean;
  published: boolean;
  published_at: number | null;
  state: PublishState;
};

export type PublishQueue = {
  generated_at: number;
  ready_count: number;
  videos: PublishVideo[];
};

export async function markPublished(projectId: string, published: boolean) {
  return apiFetch<{ project_id: string; published: boolean; published_at: number | null }>(
    "/api/publish/mark",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, published }),
    },
  );
}
