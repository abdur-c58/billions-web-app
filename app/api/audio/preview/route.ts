import { NextResponse } from "next/server";
import { getEffectiveBackendUrl } from "@/lib/backend-tunnel";

function forwardProjectHeader(request: Request) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const project = request.headers.get("X-Billions-Project");
  if (project) headers["X-Billions-Project"] = project;
  return headers;
}

export async function POST(request: Request) {
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

  let body: string;
  try {
    body = await request.text();
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  try {
    const response = await fetch(`${backendUrl}/api/audio/preview`, {
      method: "POST",
      headers: forwardProjectHeader(request),
      body,
      cache: "no-store",
    });
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
      { error: `Cannot reach Python backend (${backendUrl}). ${message}` },
      { status: 502 },
    );
  }
}
