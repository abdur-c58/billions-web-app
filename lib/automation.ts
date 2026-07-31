import { apiFetch } from "@/lib/api";

export type AutomationGoal = "none" | "fetch_review" | "auto_export";

export type AutomationSettings = {
  enabled: boolean;
};

export type AutomationStatus = {
  enabled: boolean;
  exporting_project_id: string | null;
  queue_length: number;
  queued_project_ids: string[];
  last_scan_at: number | null;
};

export async function fetchAutomationSettings() {
  return apiFetch<AutomationSettings>("/api/automation/settings");
}

export async function setAutomationEnabled(enabled: boolean) {
  return apiFetch<AutomationSettings>("/api/automation/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export async function fetchAutomationStatus() {
  return apiFetch<AutomationStatus>("/api/automation/status");
}

export async function resumeAutomation(projectId?: string) {
  return apiFetch<AutomationStatus>("/api/automation/resume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
}
