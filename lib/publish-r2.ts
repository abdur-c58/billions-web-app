import {
  GetObjectCommand,
  ListObjectsV2Command,
  PutObjectCommand,
  DeleteObjectCommand,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { getR2Client } from "@/lib/r2-client";
import type { PublishVideo } from "@/lib/publish";

/** Written by the backend (viewer/backend/publish_r2.py) once an export passes every check. */
const PUBLISH_PREFIX = "Publish/";
const MANIFEST_NAME = "publish.json";
const PUBLISHED_MARKER_NAME = "published.json";
const DOWNLOAD_URL_TTL_SECONDS = 6 * 60 * 60;
const PROJECT_ID_RE = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/;

type Manifest = Omit<PublishVideo, "published" | "published_at" | "state">;

function assertProjectId(projectId: string): void {
  if (!PROJECT_ID_RE.test(projectId)) {
    throw new Error("Invalid project id.");
  }
}

async function readJson<T>(key: string): Promise<T | null> {
  const { client, bucket } = getR2Client();
  try {
    const response = await client.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
    const raw = await response.Body?.transformToString();
    return raw ? (JSON.parse(raw) as T) : null;
  } catch (error) {
    if ((error as { name?: string })?.name === "NoSuchKey") return null;
    throw error;
  }
}

async function listManifestKeys(): Promise<string[]> {
  const { client, bucket } = getR2Client();
  const keys: string[] = [];
  let token: string | undefined;
  do {
    const page = await client.send(
      new ListObjectsV2Command({ Bucket: bucket, Prefix: PUBLISH_PREFIX, ContinuationToken: token }),
    );
    for (const item of page.Contents ?? []) {
      if (item.Key?.endsWith(`/${MANIFEST_NAME}`)) keys.push(item.Key);
    }
    token = page.IsTruncated ? page.NextContinuationToken : undefined;
  } while (token);
  return keys;
}

export async function listPublishVideos(): Promise<PublishVideo[]> {
  const keys = await listManifestKeys();
  const videos = await Promise.all(
    keys.map(async (key) => {
      const folder = key.slice(0, -MANIFEST_NAME.length);
      const [manifest, marker] = await Promise.all([
        readJson<Manifest>(key),
        readJson<{ published?: boolean; published_at?: number }>(`${folder}${PUBLISHED_MARKER_NAME}`),
      ]);
      if (!manifest) return null;
      const published = Boolean(marker?.published);
      return {
        ...manifest,
        published,
        published_at: published ? (marker?.published_at ?? null) : null,
        state: published ? "published" : "ready",
      } satisfies PublishVideo;
    }),
  );
  return videos
    .filter((video): video is PublishVideo => video !== null)
    .sort((a, b) => (b.exported_at ?? 0) - (a.exported_at ?? 0));
}

export async function setPublished(projectId: string, published: boolean) {
  assertProjectId(projectId);
  const folder = `${PUBLISH_PREFIX}${projectId}/`;
  if (!(await readJson<Manifest>(`${folder}${MANIFEST_NAME}`))) {
    throw new Error(`No video waiting to publish for project ${projectId}.`);
  }
  const { client, bucket } = getR2Client();
  const key = `${folder}${PUBLISHED_MARKER_NAME}`;
  if (published) {
    const marker = { published: true, published_at: Date.now() / 1000 };
    await client.send(
      new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        Body: JSON.stringify(marker, null, 2),
        ContentType: "application/json",
      }),
    );
    return marker;
  }
  await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: key }));
  return { published: false, published_at: null };
}

export async function publishVideoDownloadUrl(projectId: string): Promise<string> {
  assertProjectId(projectId);
  const manifest = await readJson<Manifest>(`${PUBLISH_PREFIX}${projectId}/${MANIFEST_NAME}`);
  if (!manifest?.video_key) {
    throw new Error(`No video waiting to publish for project ${projectId}.`);
  }
  const { client, bucket } = getR2Client();
  const filename = manifest.video_filename || "video.mp4";
  return getSignedUrl(
    client,
    new GetObjectCommand({
      Bucket: bucket,
      Key: manifest.video_key,
      ResponseContentType: "video/mp4",
      ResponseContentDisposition: `attachment; filename*=UTF-8''${encodeURIComponent(filename)}`,
    }),
    { expiresIn: DOWNLOAD_URL_TTL_SECONDS },
  );
}
