import { NextResponse } from "next/server";
import { getEffectiveBackendUrl } from "@/lib/backend-tunnel";

export async function GET(request: Request) {
  const backendUrl = await getEffectiveBackendUrl();
  if (!backendUrl) {
    return NextResponse.json(
      {
        error:
          "Python backend is not configured. Run npm run dev:api locally, or connect a tunnel from the Vercel app.",
      },
      { status: 503 },
    );
  }

  const jobId = new URL(request.url).searchParams.get("job_id")?.trim();
  if (!jobId) {
    return NextResponse.json({ error: "job_id is required" }, { status: 400 });
  }

  try {
    const response = await fetch(
      `${backendUrl}/api/storage/youtube-audio/status?job_id=${encodeURIComponent(jobId)}`,
      { cache: "no-store" },
    );
    const text = await response.text();
    let payload: Record<string, unknown> = {};
    try {
      payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};
    } catch {
      payload = { error: text.slice(0, 300) || "Backend returned a non-JSON response." };
    }
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Backend request failed";
    return NextResponse.json(
      {
        error: `Cannot reach Python backend (${backendUrl}). ${message}`,
      },
      { status: 502 },
    );
  }
}
