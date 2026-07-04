import { NextResponse } from "next/server";
import { getEffectiveBackendUrl } from "@/lib/backend-tunnel";

export const maxDuration = 300;

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
    const response = await fetch(`${backendUrl}/api/storage/youtube-audio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

    if (response.status === 404 && payload.error === "Not found") {
      return NextResponse.json(
        {
          error:
            "YouTube audio download is not available on the running backend. Restart it: npm run dev:api (or ytserver).",
        },
        { status: 503 },
      );
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
