import { NextResponse } from "next/server";

/** Expose client-safe runtime config (tunnel URL for large uploads, etc.). */
export async function GET() {
  const port = process.env.BROLL_BACKEND_PORT || "8766";
  const backendUrl =
    process.env.BROLL_BACKEND_URL?.replace(/\/$/, "") ||
    (process.env.VERCEL ? null : `http://127.0.0.1:${port}`);

  return NextResponse.json({
    // When set (Vercel + tunnel), the browser uploads audio directly to the
    // Python backend — bypasses Vercel's ~4.5MB request body limit on rewrites.
    audio_upload_url: backendUrl ? `${backendUrl}/api/project/upload/audio` : null,
    backend_url: backendUrl,
  });
}
