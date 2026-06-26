import { NextResponse } from "next/server";
import { isR2Configured, uploadProjectWorkspaceFile } from "@/lib/project-r2";

export async function POST(request: Request) {
  try {
    if (!isR2Configured()) {
      return NextResponse.json({ error: "R2 is not configured." }, { status: 503 });
    }

    const body = (await request.json()) as {
      name?: string;
      content_base64?: string;
      project?: string;
    };
    const name = body.name?.trim();
    const contentBase64 = body.content_base64;
    const projectId = body.project?.trim();

    if (!name || !contentBase64 || !projectId) {
      return NextResponse.json(
        { error: "name, project, and content_base64 are required." },
        { status: 400 },
      );
    }

    const buffer = Buffer.from(contentBase64, "base64");
    const result = await uploadProjectWorkspaceFile(projectId, name, buffer);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to sync project file" },
      { status: 400 },
    );
  }
}
