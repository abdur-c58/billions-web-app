import { NextResponse } from "next/server";
import { moveStorageItem } from "@/lib/r2";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { sourceKey?: string; destinationPrefix?: string };
    const sourceKey = body.sourceKey?.trim();
    const destinationPrefix = body.destinationPrefix ?? "";

    if (!sourceKey) {
      return NextResponse.json({ error: "sourceKey is required" }, { status: 400 });
    }

    const result = await moveStorageItem(sourceKey, destinationPrefix);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Move failed" },
      { status: 400 },
    );
  }
}
