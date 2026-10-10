import { NextResponse } from "next/server";
import { listPublishVideos } from "@/lib/publish-r2";

export const dynamic = "force-dynamic";

/** JSON version of the /publish page, read straight from R2. */
export async function GET(request: Request) {
  try {
    const origin = new URL(request.url).origin;
    const videos = await listPublishVideos();
    return NextResponse.json({
      generated_at: Date.now() / 1000,
      ready_count: videos.filter((video) => video.state === "ready").length,
      videos: videos.map((video) => ({
        ...video,
        download_url: `${origin}/api/publish/download/${video.project_id}`,
      })),
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to read publish queue" },
      { status: 500 },
    );
  }
}
