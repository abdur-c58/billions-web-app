import { getSessionHeaders } from "@/lib/session";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const sessionHeaders = getSessionHeaders();
  const optionHeaders =
    options.headers instanceof Headers
      ? Object.fromEntries(options.headers.entries())
      : (options.headers as Record<string, string> | undefined) ?? {};

  const resolvedUrl = await resolveBrollApiUrl(url);

  let response: Response;
  try {
    response = await fetch(resolvedUrl, {
      ...options,
      headers: {
        ...sessionHeaders,
        ...optionHeaders,
      },
    });
  } catch {
    const isDirectBackend = /^https?:\/\//i.test(resolvedUrl);
    const hint = isDirectBackend
      ? "Open Backend in the nav, paste your current trycloudflare URL, and click Connect."
      : "Run npm run dev:all (Next.js :3001 + Python API :8766), or connect a tunnel from the Vercel app.";
    throw new ApiError(`Cannot reach broll API (${resolvedUrl}). ${hint}`, 0);
  }

  let payload: Record<string, unknown> = {};
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      payload = (await response.json()) as Record<string, unknown>;
    } catch {
      payload = {};
    }
  }

  if (!response.ok) {
    const message =
      (typeof payload.error === "string" && payload.error) ||
      (response.status === 500 || response.status === 502 || response.status === 503
        ? "Broll API offline on port 8766. Run: npm run dev:all"
        : `Request failed (${response.status})`);
    throw new ApiError(message, response.status);
  }

  return payload as T;
}

export function isRetryableFetchError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  const status = error instanceof ApiError ? error.status : 0;
  return (
    status === 0 ||
    status === 429 ||
    status === 400 ||
    status >= 500 ||
    /rate|timeout|timed out|network|offline|pexels|429|503|502|504|cannot reach/i.test(
      message,
    )
  );
}

export function retryDelayMs(attempt: number, error: unknown): number {
  const status = error instanceof ApiError ? error.status : 0;
  const base = status === 429 ? 3000 : 1500;
  return Math.min(45000, Math.round(base * 1.6 ** (attempt - 1)));
}

export async function sleep(ms: number) {
  await new Promise((resolve) => window.setTimeout(resolve, ms));
}

/** POST multipart form data with upload progress (fetch has no upload progress events). */
export function uploadFormData<T>(
  url: string,
  form: FormData,
  onProgress?: (percent: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);

    const sessionHeaders = getSessionHeaders();
    for (const [key, value] of Object.entries(sessionHeaders)) {
      xhr.setRequestHeader(key, value);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };

    xhr.onload = () => {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(xhr.responseText) as Record<string, unknown>;
      } catch {
        payload = {};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload as T);
        return;
      }
      const message =
        (typeof payload.error === "string" && payload.error) ||
        (xhr.status >= 500 ? "Broll API offline. Check backend and tunnel." : `Request failed (${xhr.status})`);
      reject(new ApiError(message, xhr.status));
    };

    xhr.onerror = () => {
      const isDirectBackend = /^https?:\/\//i.test(url);
      const hint = isDirectBackend
        ? "Check that cloudflared is running and BROLL_BACKEND_URL matches the tunnel URL."
        : "Run npm run dev:all (Next.js :3001 + Python API :8766).";
      reject(new ApiError(`Cannot reach broll API (${url}). ${hint}`, 0));
    };

    xhr.send(form);
  });
}

/** Resolve API path — uses tunnel/backend URL when configured (Vercel + cloudflared). */
let cachedBackendUrl: string | null | undefined;

export function invalidateBackendUrlCache() {
  cachedBackendUrl = undefined;
}

/** Paths that must hit the Python backend directly (long-running or large payloads). */
const ALWAYS_DIRECT_BACKEND_PATHS: string[] = [];

function shouldResolveToDirectBackend(path: string, backendUrl: string): boolean {
  if (ALWAYS_DIRECT_BACKEND_PATHS.some((prefix) => path === prefix || path.startsWith(`${prefix}?`))) {
    return true;
  }
  return shouldUseDirectBackend(backendUrl);
}

function shouldUseDirectBackend(backendUrl: string): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") return false;
  if (host.endsWith(".vercel.app")) return true;
  const backendIsLocal =
    backendUrl.includes("127.0.0.1") || backendUrl.includes("localhost");
  return !backendIsLocal;
}

export async function resolveBrollApiUrl(path: string): Promise<string> {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (/^https?:\/\//i.test(normalized)) return normalized;

  if (cachedBackendUrl === undefined) {
    try {
      const config = await fetch("/api/config", { cache: "no-store" }).then(
        (response) => response.json() as Promise<{ backend_url?: string | null }>,
      );
      cachedBackendUrl = config.backend_url ?? null;
    } catch {
      cachedBackendUrl = null;
    }
  }

  if (cachedBackendUrl && shouldResolveToDirectBackend(normalized, cachedBackendUrl)) {
    return `${cachedBackendUrl}${normalized}`;
  }
  return normalized;
}

/** Python b-roll API — use for large uploads to bypass Next.js proxy body limits. */
export function getBrollBackendUrl() {
  const fromEnv = process.env.NEXT_PUBLIC_BROLL_BACKEND_URL?.replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  if (typeof window !== "undefined") {
    const port = process.env.NEXT_PUBLIC_BROLL_BACKEND_PORT || "8766";
    return `http://${window.location.hostname}:${port}`;
  }
  return "http://127.0.0.1:8766";
}
