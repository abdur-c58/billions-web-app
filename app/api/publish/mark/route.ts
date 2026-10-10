import { NextResponse } from "next/server";
import { setPublished } from "@/lib/publish-r2";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { project_id?: string; published?: boolean };
    const projectId = String(body.project_id || "").trim();
    if (!projectId) {
      return NextResponse.json({ error: "project_id is required." }, { status: 400 });
    }
    const status = await setPublished(projectId, body.published !== false);
    return NextResponse.json({ project_id: projectId, ...status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to update publish status" },
      { status: 400 },
    );
  }
}
