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

  const url = new URL(request.url);
  const headers: Record<string, string> = {};
  const project = request.headers.get("X-Billions-Project");
  if (project) headers["X-Billions-Project"] = project;

  try {
    const response = await fetch(`${backendUrl}/api/audio/preview-file${url.search}`, {
      headers,
      cache: "no-store",
    });

    if (!response.ok) {
      const text = await response.text();
      let payload: Record<string, unknown> = {};
      try {
        payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      } catch {
        payload = { error: text.slice(0, 300) || "Preview file unavailable." };
      }
      return NextResponse.json(payload, { status: response.status });
    }

    const buffer = await response.arrayBuffer();
    return new NextResponse(buffer, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "audio/mp4",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Backend request failed";
    return NextResponse.json(
      { error: `Cannot reach Python backend (${backendUrl}). ${message}` },
      { status: 502 },
    );
  }
}
