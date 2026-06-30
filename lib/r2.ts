import {
  CopyObjectCommand,
  DeleteObjectCommand,
  GetObjectCommand,
  HeadObjectCommand,
  ListObjectsV2Command,
  PutObjectCommand,
} from "@aws-sdk/client-s3";
import { Readable } from "node:stream";
import { getR2Client } from "@/lib/r2-client";

export const VIDEO_EXTENSIONS = new Set([
  ".mp4",
  ".webm",
  ".mov",
  ".avi",
  ".mkv",
  ".m4v",
  ".wmv",
  ".flv",
]);

export const AUDIO_EXTENSIONS = new Set([
  ".mp3",
  ".wav",
  ".m4a",
  ".aac",
  ".ogg",
  ".flac",
  ".wma",
]);

export const MEDIA_EXTENSIONS = new Set([...VIDEO_EXTENSIONS, ...AUDIO_EXTENSIONS]);

export const ROOT_STORAGE_FOLDERS = ["Audio", "B-Roll", "Other"] as const;
export const EXPORTED_VIDEOS_FOLDER = "Exported Videos";
export const ALL_ROOT_FOLDERS = [...ROOT_STORAGE_FOLDERS, EXPORTED_VIDEOS_FOLDER] as const;

export type StorageItem = {
  key: string;
  name: string;
  type: "folder" | "video" | "audio" | "other";
  size: number | null;
  lastModified: string | null;
  protected?: boolean;
  /** ISO date after which the file will be auto-purged (Exported Videos only) */
  expiresAt?: string | null;
  /** Whether expiry is within 24 hours */
  expiringSoon?: boolean;
};

export function normalizePrefix(prefix: string) {
  const trimmed = prefix.trim().replace(/^\/+/, "");
  if (!trimmed) return "";
  return trimmed.endsWith("/") ? trimmed : `${trimmed}/`;
}

export function classifyKey(key: string): StorageItem["type"] {
  const name = key.split("/").filter(Boolean).pop() || key;
  if (name.endsWith("/")) return "folder";
  const ext = name.includes(".") ? `.${name.split(".").pop()?.toLowerCase()}` : "";
  if (VIDEO_EXTENSIONS.has(ext)) return "video";
  if (AUDIO_EXTENSIONS.has(ext)) return "audio";
  return "other";
}

export function isProtectedRootFolder(key: string): boolean {
  const normalized = normalizePrefix(key);
  return ALL_ROOT_FOLDERS.some((name) => normalized === `${name}/`);
}

export async function ensureRootFolders() {
  const { client, bucket } = getR2Client();
  for (const name of ALL_ROOT_FOLDERS) {
    await client.send(
      new PutObjectCommand({
        Bucket: bucket,
        Key: `${name}/`,
        Body: "",
      }),
    );
  }
}

function sortStorageItems(items: StorageItem[], prefix: string) {
  if (prefix !== "") {
    return items.sort((a, b) => {
      if (a.type === "folder" && b.type !== "folder") return -1;
      if (b.type === "folder" && a.type !== "folder") return 1;
      return a.name.localeCompare(b.name);
    });
  }

  const protectedOrder = new Map(ALL_ROOT_FOLDERS.map((name, index) => [name, index]));
  return items.sort((a, b) => {
    const aProtected = protectedOrder.get(a.name as (typeof ALL_ROOT_FOLDERS)[number]);
    const bProtected = protectedOrder.get(b.name as (typeof ALL_ROOT_FOLDERS)[number]);
    if (aProtected != null && bProtected != null) return aProtected - bProtected;
    if (aProtected != null) return -1;
    if (bProtected != null) return 1;
    if (a.type === "folder" && b.type !== "folder") return -1;
    if (b.type === "folder" && a.type !== "folder") return 1;
    return a.name.localeCompare(b.name);
  });
}

export async function listStorage(prefix = "") {
  const normalized = normalizePrefix(prefix);
  if (normalized === "") {
    await ensureRootFolders();
  }

  const { client, bucket } = getR2Client();
  const response = await client.send(
    new ListObjectsV2Command({
      Bucket: bucket,
      Prefix: normalized,
      Delimiter: "/",
    }),
  );

  const folders: StorageItem[] = (response.CommonPrefixes || [])
      .filter((entry) => {
        const key = entry.Prefix || "";
        return !key.startsWith(".project/") && !key.startsWith(".config/");
      })
    .map((entry) => {
    const key = entry.Prefix || "";
    const name = key.slice(normalized.length).replace(/\/$/, "");
    return {
      key,
      name,
      type: "folder" as const,
      size: null,
      lastModified: null,
      protected: normalized === "" && ALL_ROOT_FOLDERS.includes(name as (typeof ALL_ROOT_FOLDERS)[number]),
    };
  });

  const isExportedVideosFolder = normalized === `${EXPORTED_VIDEOS_FOLDER}/`;
  const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

  const files: StorageItem[] = await Promise.all(
    (response.Contents || [])
      .filter((entry) => entry.Key && entry.Key !== normalized)
      .filter((entry) => !entry.Key!.startsWith(".project/"))
      .filter((entry) => !entry.Key!.startsWith(".config/"))
      .map(async (entry) => {
        const key = entry.Key || "";
        const name = key.slice(normalized.length);
        let expiresAt: string | null = null;
        let expiringSoon = false;
        if (isExportedVideosFolder && !key.endsWith("/")) {
          try {
            const head = await client.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
            const meta = head.Metadata ?? {};
            const lastDl = Number(meta["last-downloaded"] ?? meta["uploaded-at"] ?? 0);
            if (lastDl) {
              const expiry = new Date(lastDl * 1000 + WEEK_MS);
              expiresAt = expiry.toISOString();
              expiringSoon = expiry.getTime() - Date.now() < 24 * 60 * 60 * 1000;
            }
          } catch {
            // Metadata unavailable — skip expiry info.
          }
        }
        return {
          key,
          name,
          type: classifyKey(name),
          size: entry.Size ?? null,
          lastModified: entry.LastModified?.toISOString() ?? null,
          ...(isExportedVideosFolder && { expiresAt, expiringSoon }),
        };
      }),
  );

  return {
    prefix: normalized,
    items: sortStorageItems([...folders, ...files], normalized),
  };
}

export async function createFolder(prefix: string, folderName: string) {
  const { client, bucket } = getR2Client();
  const safeName = folderName.trim().replace(/[\\]+/g, "/").replace(/^\/+|\/+$/g, "");
  if (!safeName) {
    throw new Error("Folder name is required.");
  }
  if (normalizePrefix(prefix) === "") {
    throw new Error("Create folders inside Audio, B-Roll, or Other.");
  }
  const key = `${normalizePrefix(prefix)}${safeName}/`;
  await client.send(
    new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: "",
    }),
  );
  return { key };
}

export function isMediaItemType(type: StorageItem["type"]) {
  return type === "audio" || type === "video";
}

export function assertReadableStorageKey(key: string) {
  if (!key || key.endsWith("/")) {
    throw new Error("Invalid file key.");
  }
  const root = key.split("/")[0];
  if (!ALL_ROOT_FOLDERS.includes(root as (typeof ALL_ROOT_FOLDERS)[number])) {
    throw new Error("File is not in the storage library.");
  }
}

export function assertPreviewableKey(key: string) {
  assertReadableStorageKey(key);
  const type = classifyKey(key);
  if (!isMediaItemType(type)) {
    throw new Error("Preview is only available for audio and video files.");
  }
}

export function contentTypeForStorageName(name: string) {
  const ext = name.includes(".") ? `.${name.split(".").pop()?.toLowerCase()}` : "";
  if (ext === ".mp4") return "video/mp4";
  if (ext === ".webm") return "video/webm";
  if (ext === ".mov") return "video/quicktime";
  if (ext === ".avi") return "video/x-msvideo";
  if (ext === ".mkv") return "video/x-matroska";
  if (ext === ".m4v") return "video/x-m4v";
  if (ext === ".wmv") return "video/x-ms-wmv";
  if (ext === ".flv") return "video/x-flv";
  if (ext === ".mp3") return "audio/mpeg";
  if (ext === ".wav") return "audio/wav";
  if (ext === ".m4a") return "audio/mp4";
  if (ext === ".aac") return "audio/aac";
  if (ext === ".ogg") return "audio/ogg";
  if (ext === ".flac") return "audio/flac";
  if (ext === ".wma") return "audio/x-ms-wma";
  return "application/octet-stream";
}

function objectBodyToWebStream(body: unknown): ReadableStream<Uint8Array> {
  if (
    body &&
    typeof body === "object" &&
    "transformToWebStream" in body &&
    typeof body.transformToWebStream === "function"
  ) {
    return body.transformToWebStream() as ReadableStream<Uint8Array>;
  }
  return Readable.toWeb(body as Readable) as ReadableStream<Uint8Array>;
}

export async function getStorageObject(
  key: string,
  options?: { range?: string; download?: boolean },
) {
  if (!key.startsWith(".project/")) {
    assertReadableStorageKey(key);
  }
  const { client, bucket } = getR2Client();
  const name = key.split("/").pop() || "download";
  const safeName = name.replace(/["\r\n]/g, "_");
  const response = await client.send(
    new GetObjectCommand({
      Bucket: bucket,
      Key: key,
      Range: options?.range,
      ResponseContentDisposition: options?.download
        ? `attachment; filename="${safeName}"`
        : undefined,
    }),
  );

  if (!response.Body) {
    throw new Error("File is empty or unavailable.");
  }

  return {
    body: objectBodyToWebStream(response.Body),
    contentType: response.ContentType || contentTypeForStorageName(name),
    contentLength: response.ContentLength,
    contentRange: response.ContentRange,
    acceptRanges: response.AcceptRanges,
    status: response.ContentRange ? 206 : 200,
  };
}

export async function uploadObject(key: string, body: Buffer, contentType: string) {
  const { client, bucket } = getR2Client();
  await client.send(
    new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: body,
      ContentType: contentType,
    }),
  );
  return { key };
}

export async function deleteObject(key: string) {
  if (isProtectedRootFolder(key)) {
    throw new Error("This root folder cannot be deleted.");
  }
  if (key.startsWith(".project/")) {
    throw new Error("Project files cannot be deleted from the library browser.");
  }
  const { client, bucket } = getR2Client();
  await client.send(
    new DeleteObjectCommand({
      Bucket: bucket,
      Key: key,
    }),
  );
}

async function listAllKeys(prefix: string): Promise<string[]> {
  const { client, bucket } = getR2Client();
  const keys: string[] = [];
  let continuationToken: string | undefined;

  do {
    const response = await client.send(
      new ListObjectsV2Command({
        Bucket: bucket,
        Prefix: prefix,
        ContinuationToken: continuationToken,
      }),
    );
    for (const entry of response.Contents || []) {
      if (entry.Key) keys.push(entry.Key);
    }
    continuationToken = response.IsTruncated ? response.NextContinuationToken : undefined;
  } while (continuationToken);

  return keys;
}

async function copyObject(sourceKey: string, destinationKey: string) {
  const { client, bucket } = getR2Client();
  const copySource = `${bucket}/${sourceKey.split("/").map(encodeURIComponent).join("/")}`;
  await client.send(
    new CopyObjectCommand({
      Bucket: bucket,
      CopySource: copySource,
      Key: destinationKey,
    }),
  );
}

function folderBaseName(key: string) {
  return key.replace(/\/$/, "").split("/").pop() || "";
}

export async function moveStorageItem(sourceKey: string, destinationPrefix: string) {
  if (isProtectedRootFolder(sourceKey)) {
    throw new Error("This root folder cannot be moved.");
  }

  const destPrefix = normalizePrefix(destinationPrefix);
  if (!destPrefix) {
    throw new Error("Choose a destination folder inside Audio, B-Roll, or Other.");
  }

  const isFolder = sourceKey.endsWith("/");
  const itemName = isFolder ? folderBaseName(sourceKey) : sourceKey.split("/").pop() || "";

  if (!itemName) {
    throw new Error("Invalid item path.");
  }

  const destinationKey = `${destPrefix}${itemName}${isFolder ? "/" : ""}`;

  if (destinationKey === sourceKey) {
    throw new Error("Item is already in this location.");
  }

  if (isFolder && destPrefix.startsWith(sourceKey)) {
    throw new Error("Cannot move a folder into itself or its subfolder.");
  }

  if (isFolder) {
    const keys = await listAllKeys(sourceKey);
    if (keys.length === 0) {
      await copyObject(sourceKey, destinationKey);
      await deleteObject(sourceKey);
      return { key: destinationKey };
    }

    for (const key of keys) {
      const relative = key.slice(sourceKey.length);
      const nextKey = `${destinationKey}${relative}`;
      await copyObject(key, nextKey);
    }

    for (const key of [...keys].reverse()) {
      await deleteObject(key);
    }
    return { key: destinationKey };
  }

  await copyObject(sourceKey, destinationKey);
  await deleteObject(sourceKey);
  return { key: destinationKey };
}
