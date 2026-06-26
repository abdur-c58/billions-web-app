import { NextResponse } from "next/server";
import { createFolder, listStorage } from "@/lib/r2";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const prefix = searchParams.get("prefix") || "";
    const payload = await listStorage(prefix);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to list storage" },
      { status: 500 },
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { prefix?: string; folderName?: string };
    const prefix = body.prefix || "";
    const folderName = body.folderName || "";
    const result = await createFolder(prefix, folderName);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to create folder" },
      { status: 400 },
    );
  }
}
