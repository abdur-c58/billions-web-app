import { apiFetch } from "@/lib/api";
import type { ExportSnapshot } from "@/lib/types";

export async function fetchExportStatus(projectId: string): Promise<ExportSnapshot> {
  return apiFetch<ExportSnapshot>("/api/export/status", {
    headers: { "X-Billions-Project": projectId },
  });
}
