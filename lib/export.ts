import { apiFetch } from "@/lib/api";
import type { ExportSnapshot } from "@/lib/types";

export async function fetchExportStatus(projectId: string): Promise<ExportSnapshot> {
  return apiFetch<ExportSnapshot>("/api/export/status", {
    headers: { "X-Billions-Project": projectId },
  });
}

export type YoutubeChapter = {
  title: string;
  timestamp: string;
  start_seconds: number;
};

export type YoutubeChapters = {
  project_id: string;
  chapters: YoutubeChapter[];
  text: string;
};

export async function fetchYoutubeChapters(projectId?: string): Promise<YoutubeChapters> {
  return apiFetch<YoutubeChapters>("/api/export/chapters", {
    headers: projectId ? { "X-Billions-Project": projectId } : undefined,
  });
}

export async function regenerateYoutubeDescription(
  includeEmojis: boolean,
  includeChapters: boolean,
): Promise<ExportSnapshot> {
  return apiFetch<ExportSnapshot>("/api/export/youtube-description", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      include_emojis: includeEmojis,
      include_chapters: includeChapters,
    }),
  });
}

export async function regenerateThumbnailPrompts(): Promise<ExportSnapshot> {
  return apiFetch<ExportSnapshot>("/api/export/thumbnail-prompts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}
