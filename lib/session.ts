const PROJECT_KEY = "billions_project";
const PROJECT_LABEL_KEY = "billions_project_label";

export function readStoredProject(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(PROJECT_KEY);
}

export function storeProject(projectId: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(PROJECT_KEY, projectId);
}

export function storeProjectLabel(label: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(PROJECT_LABEL_KEY, label);
}

export function readStoredProjectLabel(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(PROJECT_LABEL_KEY);
}

export function clearStoredProject() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(PROJECT_KEY);
  localStorage.removeItem(PROJECT_LABEL_KEY);
}

export function clearSession() {
  clearStoredProject();
}

export function getSessionHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const project = readStoredProject();
  const headers: Record<string, string> = {};
  if (project) headers["X-Billions-Project"] = project;
  return headers;
}
