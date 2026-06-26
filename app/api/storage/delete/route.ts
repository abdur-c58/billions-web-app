import { NextResponse } from "next/server";
import { deleteObject } from "@/lib/r2";

export async function DELETE(request: Request) {
  try {
    const body = (await request.json()) as { key?: string };
    const key = body.key?.trim();
    if (!key) {
      return NextResponse.json({ error: "key is required" }, { status: 400 });
    }
    await deleteObject(key);
    return NextResponse.json({ ok: true, key });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Delete failed" },
      { status: 500 },
    );
  }
}
