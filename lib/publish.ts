import type { ScriptThumbnail } from "@/lib/types";

export type PublishState = "ready" | "published";

/** One video in the R2 Publish/ folder (see viewer/backend/publish_r2.py). */
export type PublishVideo = {
  project_id: string;
  title: string;
  channel: string;
  thumbnail: ScriptThumbnail | null;
  /** Script's `youtube_description`, without chapters. Missing on videos synced before it existed. */
  youtube_description?: string;
  chapters: { title: string; timestamp: string; start_seconds: number }[];
  chapters_text: string;
  video_key: string;
  video_filename: string;
  video_size_bytes: number;
  exported_at: number | null;
  synced_at: number | null;
  published: boolean;
  published_at: number | null;
  state: PublishState;
};

/** Plain fetch: these routes live on the website itself, not the Python backend. */
export async function markPublished(projectId: string, published: boolean) {
  const response = await fetch("/api/publish/mark", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, published }),
  });
  const payload = (await response.json().catch(() => ({}))) as { error?: string };
  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload;
}
