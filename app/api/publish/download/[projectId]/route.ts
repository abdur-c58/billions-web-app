import { NextResponse } from "next/server";
import { publishVideoDownloadUrl } from "@/lib/publish-r2";

export const dynamic = "force-dynamic";

/** Stable download link: redirects to a fresh short-lived signed R2 URL for the MP4. */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ projectId: string }> },
) {
  try {
    const { projectId } = await params;
    const url = await publishVideoDownloadUrl(projectId);
    return NextResponse.redirect(url, 302);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Download unavailable" },
      { status: 404 },
    );
  }
}
