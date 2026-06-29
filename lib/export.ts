import { apiFetch } from "@/lib/api";
import type { ExportSnapshot } from "@/lib/types";

export async function fetchExportStatus(projectId: string): Promise<ExportSnapshot> {
  return apiFetch<ExportSnapshot>("/api/export/status", {
    headers: { "X-Billions-Project": projectId },
  });
}

export async function regenerateYoutubeDescription(
  includeEmojis: boolean,
): Promise<ExportSnapshot> {
  return apiFetch<ExportSnapshot>("/api/export/youtube-description", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_emojis: includeEmojis }),
  });
}
