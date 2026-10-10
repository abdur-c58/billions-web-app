import { apiFetch } from "@/lib/api";
import type { ExportSnapshot, ScriptThumbnail } from "@/lib/types";

export type ScriptThumbnailResponse = {
  project_id: string;
  thumbnail: ScriptThumbnail | null;
};

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

export async function fetchScriptThumbnail(projectId?: string): Promise<ScriptThumbnailResponse> {
  return apiFetch<ScriptThumbnailResponse>("/api/export/thumbnail", {
    headers: projectId ? { "X-Billions-Project": projectId } : undefined,
  });
}
