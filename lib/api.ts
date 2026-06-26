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

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        ...sessionHeaders,
        ...optionHeaders,
      },
    });
  } catch {
    throw new ApiError(
      "Cannot reach broll API on port 8766. Run: npm run dev:all",
      0,
    );
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
