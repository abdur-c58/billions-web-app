import { NextRequest, NextResponse } from "next/server";
import { isR2Configured, listProjectWorkspaceFiles } from "@/lib/project-r2";

export async function GET(request: NextRequest) {
  try {
    if (!isR2Configured()) {
      return NextResponse.json({
        items: [],
        ttlDays: 7,
        configured: false,
      });
    }
    const projectId = request.nextUrl.searchParams.get("project")?.trim() || undefined;
    const payload = await listProjectWorkspaceFiles({ projectId });
    return NextResponse.json({ ...payload, configured: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to list project files" },
      { status: 500 },
    );
  }
}
