import { NextResponse } from "next/server";
import {
  AUDIO_EXTENSIONS,
  MEDIA_EXTENSIONS,
  normalizePrefix,
  uploadObject,
  VIDEO_EXTENSIONS,
} from "@/lib/r2";

function contentTypeForName(name: string) {
  const ext = name.includes(".") ? `.${name.split(".").pop()?.toLowerCase()}` : "";
  if (ext === ".mp4") return "video/mp4";
  if (ext === ".webm") return "video/webm";
  if (ext === ".mov") return "video/quicktime";
  if (ext === ".mp3") return "audio/mpeg";
  if (ext === ".wav") return "audio/wav";
  if (ext === ".m4a") return "audio/mp4";
  if (ext === ".ogg") return "audio/ogg";
  if (ext === ".flac") return "audio/flac";
  return "application/octet-stream";
}

export async function POST(request: Request) {
  try {
    const form = await request.formData();
    const prefix = String(form.get("prefix") || "");
    const file = form.get("file");
    if (!(file instanceof File)) {
      return NextResponse.json({ error: "Missing file" }, { status: 400 });
    }

    if (normalizePrefix(prefix) === "") {
      return NextResponse.json(
        { error: "Upload files inside Audio, B-Roll, or Other." },
        { status: 400 },
      );
    }

    const ext = file.name.includes(".") ? `.${file.name.split(".").pop()?.toLowerCase()}` : "";
    if (!MEDIA_EXTENSIONS.has(ext)) {
      const allowed = [...VIDEO_EXTENSIONS, ...AUDIO_EXTENSIONS].sort().join(", ");
      return NextResponse.json(
        { error: `Unsupported file type. Allowed: ${allowed}` },
        { status: 400 },
      );
    }

    const key = `${normalizePrefix(prefix)}${file.name}`;
    const buffer = Buffer.from(await file.arrayBuffer());
    await uploadObject(key, buffer, file.type || contentTypeForName(file.name));
    return NextResponse.json({ key, name: file.name });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Upload failed" },
      { status: 500 },
    );
  }
}
