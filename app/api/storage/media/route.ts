import { NextResponse } from "next/server";
import {
  assertPreviewableKey,
  assertReadableStorageKey,
  classifyKey,
  getStorageObject,
  isMediaItemType,
} from "@/lib/r2";
import { isProjectStorageKey } from "@/lib/project-r2";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const key = searchParams.get("key");
    if (!key) {
      return NextResponse.json({ error: "Missing file key." }, { status: 400 });
    }

    const download = searchParams.get("download") === "1";

    if (isProjectStorageKey(key)) {
      const range = request.headers.get("range") ?? undefined;
      const object = await getStorageObject(key, { range, download: true });
      const headers = new Headers();
      headers.set("Content-Type", object.contentType);
      if (object.contentLength != null) {
        headers.set("Content-Length", String(object.contentLength));
      }
      if (object.contentRange) {
        headers.set("Content-Range", object.contentRange);
      }
      headers.set("Accept-Ranges", object.acceptRanges || "bytes");
      headers.set("Cache-Control", "private, max-age=3600");
      const fileName = key.split("/").pop() || "download";
      headers.set(
        "Content-Disposition",
        download ? `attachment; filename="${fileName}"` : "inline",
      );
      return new NextResponse(object.body, { status: object.status, headers });
    }

    if (download) {
      assertReadableStorageKey(key);
      if (!isMediaItemType(classifyKey(key))) {
        return NextResponse.json(
          { error: "Direct download is only available for audio and video files." },
          { status: 400 },
        );
      }
    } else {
      assertPreviewableKey(key);
    }

    const range = request.headers.get("range") ?? undefined;
    const object = await getStorageObject(key, { range, download });
    const headers = new Headers();
    headers.set("Content-Type", object.contentType);
    if (object.contentLength != null) {
      headers.set("Content-Length", String(object.contentLength));
    }
    if (object.contentRange) {
      headers.set("Content-Range", object.contentRange);
    }
    headers.set("Accept-Ranges", object.acceptRanges || "bytes");
    headers.set("Cache-Control", "private, max-age=3600");
    if (!download) {
      headers.set("Content-Disposition", "inline");
    }

    return new NextResponse(object.body, { status: object.status, headers });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to load media" },
      { status: 400 },
    );
  }
}
